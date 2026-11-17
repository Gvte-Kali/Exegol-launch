import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallationTests(unittest.TestCase):
    def test_local_install_update_and_collision(self):
        with tempfile.TemporaryDirectory(prefix='launcher test ') as tmp:
            base = Path(tmp)
            env = dict(os.environ, EXEGOL_LAUNCH_HOME=str(base / 'app'), EXEGOL_LAUNCH_BIN=str(base / 'bin'), EXEGOL_LAUNCH_SOURCE_DIR=str(ROOT))
            for _ in range(2):
                subprocess.run(['bash', str(ROOT / 'install.sh')], env=env, check=True, capture_output=True)
                version = subprocess.check_output([str(base / 'bin/launch'), '--version'], text=True)
                self.assertIn('Exegol-launch', version)
            self.assertTrue((base / 'app/current').is_symlink())
            (base / 'bin/launch').write_text('#!/bin/sh\necho unrelated\n')
            result = subprocess.run(['bash', str(ROOT / 'install.sh')], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('unrelated', (base / 'bin/launch').read_text())

    def test_hook_preserves_existing_script_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            resources = Path(tmp)
            (resources / 'setup').mkdir()
            hook = resources / 'setup/load_user_setup.sh'
            original = '#!/bin/bash\n# Existing Exeflow setup\necho exeflow\nexit 0\n'
            hook.write_text(original)
            env = dict(os.environ, EXEGOL_LAUNCH_SOURCE_DIR=str(ROOT))
            for _ in range(2):
                subprocess.run(['bash', str(ROOT / 'setup-exegol.sh'), tmp], env=env, check=True, capture_output=True)
            text = hook.read_text()
            self.assertEqual(text.count('# BEGIN Exegol-launch'), 1)
            self.assertIn(original.split('\n', 1)[1], text)
            self.assertLess(text.index('# BEGIN Exegol-launch'), text.index('exit 0'))
            self.assertEqual(len(list((resources / 'setup').glob('load_user_setup.sh.bak-*'))), 2)
            subprocess.run(['bash', '-n', str(hook)], check=True)
            payloads = list((resources / 'setup').glob('.exegol-launch.*'))
            self.assertEqual(len(payloads), 2)
            self.assertTrue(all((p / 'exegol_launch/core.py').exists() for p in payloads))
