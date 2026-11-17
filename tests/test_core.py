import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from exegol_launch.core import Application, discover, expand_exec, launch_app


class CoreTests(unittest.TestCase):
    def test_exec_placeholders_and_quoted_arguments(self):
        self.assertEqual(expand_exec('tool "hello world" %U %i %c %k %%', 'My App', '/a.desktop', 'icon'), ['tool', 'hello world', '--icon', 'icon', 'My App', '/a.desktop', '%'])

    def test_xdg_override_hidden_and_custom_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            user, system = root / 'user', root / 'system'
            for folder in (user, system):
                (folder / 'applications').mkdir(parents=True)
            (system / 'applications/a.desktop').write_text('[Desktop Entry]\nName=System\nExec=echo hi\n')
            (user / 'applications/a.desktop').write_text('[Desktop Entry]\nHidden=true\n')
            (system / 'applications/b.desktop').write_text('[Desktop Entry]\nName=Visible\nExec=echo %U\nTerminal=true\n')
            config = root / 'config/exegol-launch'
            config.mkdir(parents=True)
            (config / 'apps.json').write_text(json.dumps([{'name': 'Custom', 'argv': ['echo', 'a; touch /tmp/never']}]))
            with patch.dict(os.environ, {'XDG_DATA_HOME': str(user), 'XDG_DATA_DIRS': str(system), 'XDG_CONFIG_HOME': str(root / 'config')}):
                apps, warnings = discover()
            self.assertFalse(warnings)
            self.assertNotIn('System', [a.name for a in apps])
            self.assertTrue(next(a for a in apps if a.name == 'Visible').terminal)
            self.assertEqual(next(a for a in apps if a.name == 'Custom').argv, ['echo', 'a; touch /tmp/never'])

    def test_detached_launch_inherits_environment_and_does_not_use_shell(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp, 'DISPLAY': ':77'}):
            with patch('exegol_launch.core.subprocess.Popen') as popen:
                path = launch_app(Application('test', 'Test', ['echo', 'literal; value']))
                args, kwargs = popen.call_args
                self.assertEqual(args[0], ['echo', 'literal; value'])
                self.assertTrue(kwargs['start_new_session'])
                self.assertNotIn('shell', kwargs)
                self.assertNotIn('env', kwargs)
                self.assertTrue(path.exists())

    def test_real_process_survives_launcher_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'done'
            child = f"import time,pathlib; time.sleep(.15); pathlib.Path({str(marker)!r}).write_text('ok')"
            code = f"from exegol_launch.core import Application, launch_app; import sys; launch_app(Application('test', 'Test', [sys.executable, '-c', {child!r}]))"
            env = dict(os.environ, XDG_STATE_HOME=tmp)
            subprocess.run(['python3', '-c', code], env=env, check=True)
            import time
            deadline = time.monotonic() + 3
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertEqual(marker.read_text(), 'ok')

if __name__ == '__main__':
    unittest.main()
