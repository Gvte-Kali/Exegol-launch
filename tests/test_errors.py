"""Regression tests for malformed configuration and operational failures."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from exegol_launch.core import Application, discover, launch_app, state_dir

ROOT = Path(__file__).resolve().parents[1]


class ErrorHandlingTests(unittest.TestCase):
    """Failures should be reported without losing unrelated valid applications."""

    def test_bad_json_entries_do_not_hide_valid_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / 'exegol-launch'
            config.mkdir()
            entries = [None, {'name': 'Bad terminal', 'argv': ['echo'], 'terminal': 'false'},
                       {'name': 'Bad cwd', 'argv': ['echo'], 'cwd': []},
                       {'name': 'Bad argument', 'argv': ['echo', '\0']},
                       {'name': 'Valid', 'argv': ['echo']},
                       {'name': 'Valid', 'argv': ['false']},
                       {'name': 'Also valid', 'argv': ['echo']}]
            (config / 'apps.json').write_text(json.dumps(entries))
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp, 'XDG_DATA_HOME': tmp, 'XDG_DATA_DIRS': tmp}):
                apps, warnings = discover()
            custom = [app for app in apps if app.id.startswith('custom:')]
            self.assertEqual([app.name for app in custom], ['Also valid', 'Valid'])
            self.assertEqual(len(warnings), 5)
            self.assertEqual(next(app for app in custom if app.name == 'Valid').argv, ['echo'])

    def test_invalid_utf8_is_reported_for_desktop_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'applications').mkdir()
            (root / 'applications/broken.desktop').write_bytes(b'\xff')
            (root / 'exegol-launch').mkdir()
            (root / 'exegol-launch/apps.json').write_bytes(b'\xff')
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': tmp, 'XDG_DATA_HOME': tmp, 'XDG_DATA_DIRS': tmp}):
                _, warnings = discover()
            self.assertEqual(len(warnings), 2)

    def test_unavailable_state_directory_has_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / 'not-a-directory'
            blocker.write_text('blocked')
            with patch.dict(os.environ, {'XDG_STATE_HOME': str(blocker)}):
                with self.assertRaisesRegex(OSError, 'Cannot create state directory'):
                    state_dir()

    def test_missing_working_directory_fails_before_starting_process(self):
        with patch('exegol_launch.core.subprocess.Popen') as popen:
            with self.assertRaisesRegex(ValueError, 'Working directory'):
                launch_app(Application('bad', 'Bad', ['echo'], cwd='/nonexistent-exegol-launch-test'))
            popen.assert_not_called()

    def test_invalid_terminal_prefix_is_explained(self):
        for terminal in ('   ', '"unterminated', '/missing-exegol-launch-terminal -e'):
            with self.subTest(terminal=terminal), patch.dict(os.environ, {'EXEGOL_LAUNCH_TERMINAL': terminal}):
                with self.assertRaisesRegex(ValueError, 'EXEGOL_LAUNCH_TERMINAL'):
                    launch_app(Application('terminal', 'Terminal', ['echo'], terminal=True))

    def test_missing_executable_has_application_and_log_context(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp}):
            with self.assertRaisesRegex(OSError, 'Unable to start Missing.*Log:'):
                launch_app(Application('missing', 'Missing', ['/missing-exegol-launch-tool']))

    def test_log_names_are_bounded_and_collision_resistant(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp}):
            with patch('exegol_launch.core.subprocess.Popen'):
                first = launch_app(Application('a/b', 'First', ['echo']))
                second = launch_app(Application('a:b', 'Second', ['echo']))
                long = launch_app(Application('a' * 1000, 'Long', ['echo']))
            self.assertNotEqual(first, second)
            self.assertLess(len(long.name), 255)

    def test_started_callback_receives_process_for_monitoring(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp}):
            with patch('exegol_launch.core.subprocess.Popen') as popen:
                seen = []
                path = launch_app(Application('test', 'Test', ['echo']), on_started=lambda process, log: seen.append((process, log)))
                self.assertEqual(seen, [(popen.return_value, path)])

    def test_cli_without_display_has_clean_error(self):
        env = dict(os.environ)
        env.pop('DISPLAY', None)
        env.pop('WAYLAND_DISPLAY', None)
        result = subprocess.run([sys.executable, '-m', 'exegol_launch'], cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('No graphical display', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_incomplete_local_update_keeps_previous_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = dict(os.environ, EXEGOL_LAUNCH_HOME=str(root / 'app'), EXEGOL_LAUNCH_BIN=str(root / 'bin'), EXEGOL_LAUNCH_SOURCE_DIR=str(ROOT))
            subprocess.run(['bash', str(ROOT / 'install.sh')], env=env, check=True, capture_output=True)
            previous = (root / 'app/current').resolve()
            incomplete = root / 'incomplete/exegol_launch'
            incomplete.mkdir(parents=True)
            (incomplete / '__init__.py').write_text('')
            env['EXEGOL_LAUNCH_SOURCE_DIR'] = str(incomplete.parent)
            result = subprocess.run(['bash', str(ROOT / 'install.sh')], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((root / 'app/current').resolve(), previous)
            self.assertEqual(len(list((root / 'app/releases').iterdir())), 1)
            self.assertIn('failed at line', result.stderr)

    def test_invalid_existing_hook_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            setup = Path(tmp) / 'setup'
            setup.mkdir()
            hook = setup / 'load_user_setup.sh'
            original = '#!/bin/bash\nif then broken\n'
            hook.write_text(original)
            env = dict(os.environ, EXEGOL_LAUNCH_SOURCE_DIR=str(ROOT))
            result = subprocess.run(['bash', str(ROOT / 'setup-exegol.sh'), tmp], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(hook.read_text(), original)
            self.assertEqual(list(setup.glob('.exegol-launch.*')), [])

    def test_wrapper_activation_failure_restores_previous_release(self):
        """Inject an activation failure into the installer's actual Python block."""
        script = (ROOT / 'install.sh').read_text()
        activation = script.split("<<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / 'app'
            base.mkdir()
            old, new = base / 'old', base / 'new'
            old.mkdir()
            new.mkdir()
            current = base / 'current'
            current.symlink_to(old)
            wrapper = root / 'launch'
            wrapper.write_text('old wrapper')
            real_replace = os.replace

            def fail_wrapper(source, target):
                if Path(target) == wrapper:
                    raise PermissionError('simulated wrapper activation failure')
                return real_replace(source, target)

            with patch.object(sys, 'argv', ['installer', str(base), str(wrapper), sys.executable, str(new)]):
                with patch('os.replace', side_effect=fail_wrapper):
                    with self.assertRaisesRegex(PermissionError, 'simulated'):
                        exec(compile(activation, 'installer-activation', 'exec'), {})
            self.assertEqual(current.resolve(), old)
            self.assertEqual(wrapper.read_text(), 'old wrapper')
            self.assertEqual(list(root.glob('.launch-*')), [])
