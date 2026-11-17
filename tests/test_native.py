"""Exercise native launch, host registration and Caido overrides without a GUI."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class NativeTests(unittest.TestCase):
    def environment(self, root):
        """Provide a harmless appfinder stand-in and isolated installation paths."""
        binary = root / 'bin'
        binary.mkdir(exist_ok=True)
        app = binary / 'xfce4-appfinder'
        app.write_text('#!/bin/sh\nprintf "%s\\n" "$DISPLAY" "$@"\n')
        app.chmod(0o755)
        return dict(os.environ, HOME=str(root), PATH=str(binary) + ':' + os.environ['PATH'], DISPLAY=':77',
                    EXEGOL_LAUNCH_HOME=str(root / 'app'), EXEGOL_LAUNCH_BIN=str(binary),
                    EXEGOL_LAUNCH_SOURCE_DIR=str(ROOT), XDG_STATE_HOME=str(root / 'state'))

    def test_install_update_and_foreground_preserve_display(self):
        with tempfile.TemporaryDirectory(prefix='native test ') as tmp:
            root = Path(tmp)
            env = self.environment(root)
            for _ in range(2):
                subprocess.run(['bash', str(ROOT / 'install.sh')], env=env, check=True, capture_output=True)
            result = subprocess.check_output([str(root / 'bin/launch'), '--foreground', '--collapsed'], env=env, text=True)
            self.assertEqual(result.splitlines(), [':77', '--disable-server', '--collapsed'])
            self.assertFalse((root / 'app/native.previous').exists())
            self.assertEqual(list((root / 'app').glob('.staging.*')), [])

    def test_unrelated_command_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self.environment(root)
            (root / 'bin/launch').write_text('unrelated')
            result = subprocess.run(['bash', str(ROOT / 'install.sh')], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((root / 'bin/launch').read_text(), 'unrelated')

    def test_registration_honors_config_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self.environment(root)
            resources = root / 'custom resources'
            (root / '.exegol').mkdir()
            (root / '.exegol/config.yml').write_text(f"volumes:\n  my_resources_path: '{resources}'\n")
            setup = resources / 'setup'
            setup.mkdir(parents=True)
            hook = setup / 'load_user_setup.sh'
            original = '#!/bin/bash\n# Existing Exeflow setup\necho existing\nexit 0\n'
            hook.write_text(original)
            hook.chmod(0o644)
            for _ in range(3):
                subprocess.run(['bash', str(ROOT / 'setup-exegol.sh')], env=env, check=True, capture_output=True)
            text = hook.read_text()
            self.assertEqual(text.count('# BEGIN Exegol-launch'), 1)
            self.assertIn(original.split('\n', 1)[1], text)
            self.assertTrue(hook.stat().st_mode & 0o100)
            self.assertEqual(len(list(setup.glob('*.bak'))), 1)
            self.assertEqual(len(list(setup.glob('exegol-launch'))), 1)
            self.assertFalse((setup / '.exegol-launch.previous').exists())
            self.assertEqual(list(setup.glob('.launch-stage-*')), [])
            subprocess.run(['bash', '-n', str(hook)], check=True)

    def test_duplicate_old_blocks_are_collapsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self.environment(root)
            setup = root / 'resources/setup'
            setup.mkdir(parents=True)
            block = '# BEGIN Exegol-launch\necho old\n# END Exegol-launch\n'
            (setup / 'load_user_setup.sh').write_text('#!/bin/bash\n' + block * 2 + 'echo keep\n')
            subprocess.run(['bash', str(ROOT / 'setup-exegol.sh'), str(setup.parent)], env=env, check=True, capture_output=True)
            text = (setup / 'load_user_setup.sh').read_text()
            self.assertEqual(text.count('# BEGIN Exegol-launch'), 1)
            self.assertIn('echo keep', text)

    def test_registration_failure_preserves_old_hook_and_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self.environment(root)
            resources = root / 'resources'
            subprocess.run(['bash', str(ROOT / 'setup-exegol.sh'), str(resources)], env=env, check=True, capture_output=True)
            hook = resources / 'setup/load_user_setup.sh'
            previous = hook.read_bytes()
            env['EXEGOL_LAUNCH_SOURCE_DIR'] = str(root / 'missing')
            result = subprocess.run(['bash', str(ROOT / 'setup-exegol.sh'), str(resources)], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(hook.read_bytes(), previous)
            self.assertTrue((resources / 'setup/exegol-launch/install.sh').is_file())

    def test_missing_display_has_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.environment(Path(tmp))
            env.pop('DISPLAY', None)
            env.pop('WAYLAND_DISPLAY', None)
            result = subprocess.run(['bash', str(ROOT / 'launch.sh')], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('No display configured', result.stderr)

    def test_caido_override_is_local_and_idempotent(self):
        spec = importlib.util.spec_from_file_location('fix_caido', ROOT / 'fix-caido.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            system = root / 'system/applications'
            system.mkdir(parents=True)
            original = '[Desktop Entry]\nName=Caido\nExec=/opt/Caido/caido %U\nType=Application\n'
            (system / 'caido.desktop').write_text(original)
            env = {'XDG_DATA_HOME': str(root / 'user'), 'XDG_DATA_DIRS': str(system.parent)}
            with patch.dict(os.environ, env), patch.object(module.os, 'geteuid', return_value=0):
                module.fix()
                module.fix()
            self.assertEqual((system / 'caido.desktop').read_text(), original)
            updated = (root / 'user/applications/caido.desktop').read_text()
            self.assertEqual(updated.count('--no-sandbox'), 1)

    def test_migration_replaces_managed_python_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self.environment(root)
            old = root / 'app/releases/old'
            old.mkdir(parents=True)
            (root / 'app/current').symlink_to(old)
            (root / 'bin/launch').write_text('#!/bin/sh\n# Managed by Exegol-launch\nexit 0\n')
            subprocess.run(['bash', str(ROOT / 'install.sh')], env=env, check=True, capture_output=True)
            self.assertFalse((root / 'app/current').is_symlink())
            self.assertFalse((root / 'app/releases').exists())
            self.assertIn('0.2.0', subprocess.check_output([str(root / 'bin/launch'), '--version'], env=env, text=True))

    def test_failed_native_update_preserves_current_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = self.environment(root)
            subprocess.run(['bash', str(ROOT / 'install.sh')], env=env, check=True, capture_output=True)
            previous = (root / 'app/native/launch.sh').read_bytes()
            env['EXEGOL_LAUNCH_SOURCE_DIR'] = str(root / 'missing')
            result = subprocess.run(['bash', str(ROOT / 'install.sh')], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((root / 'app/native/launch.sh').read_bytes(), previous)
            self.assertTrue((root / 'bin/launch').is_file())
