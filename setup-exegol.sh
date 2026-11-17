#!/usr/bin/env bash
# Run on the host as the Exegol user. Keep one managed hook block and one payload.
set -Eeuo pipefail
trap 'code=$?; printf "Exegol-launch registration failed at line %s (status %s).\n" "$LINENO" "$code" >&2; exit "$code"' ERR
command -v python3 >/dev/null || { echo 'Python 3 is required on the host.' >&2; exit 1; }
python3 - "${1:-${EXEGOL_MY_RESOURCES:-}}" <<'PY'
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request


def resources_path(explicit):
    """Honor an explicit path first, then Exegol's volumes.my_resources_path."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    config = Path(os.environ.get('EXEGOL_CONFIG_FILE', str(Path.home() / '.exegol/config.yml')))
    if not config.exists():
        return Path.home() / '.exegol/my-resources'
    text = config.read_text(encoding='utf-8')
    try:
        import yaml
    except ImportError:
        # Support the normal generated mapping without requiring PyYAML on the host.
        # Reject ambiguous YAML instead of silently writing into the wrong directory.
        in_volumes = False
        for line in text.splitlines():
            if re.match(r'^volumes:\s*(?:#.*)?$', line):
                in_volumes = True
                continue
            if line and not line[0].isspace() and not line.startswith('#'):
                in_volumes = False
            match = re.match(r'^\s+my_resources_path:\s*(.*?)\s*$', line) if in_volumes else None
            if not match:
                continue
            value = match.group(1)
            if value.startswith('"'):
                value, remainder = json.JSONDecoder().raw_decode(value)
                if remainder.strip() and not remainder.lstrip().startswith('#'):
                    raise ValueError('Unsupported resource path in config; pass the path explicitly.')
            elif value.startswith("'"):
                match = re.fullmatch(r"'((?:[^']|'')*)'\s*(?:#.*)?", value)
                if not match:
                    raise ValueError('Unsupported quoted resource path; pass it explicitly.')
                value = match.group(1).replace("''", "'")
            else:
                value = value.split(' #', 1)[0].strip()
                if not value or value[0] in '&*!{[>|' or value in ('null', '~'):
                    raise ValueError('Unsupported YAML resource path; pass it explicitly.')
            return Path(value).expanduser().resolve()
        if 'my_resources_path' in text:
            raise ValueError('Cannot parse configured resources path; pass it explicitly.')
        return Path.home() / '.exegol/my-resources'
    else:
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError('Exegol config must be a mapping; pass a resource path explicitly.')
        volumes = data.get('volumes', {})
        if not isinstance(volumes, dict):
            raise ValueError('Invalid volumes configuration.')
        value = volumes.get('my_resources_path', str(Path.home() / '.exegol/my-resources'))
        if not isinstance(value, str) or not value:
            raise ValueError('Configured my_resources_path must be a non-empty string.')
        return Path(value).expanduser().resolve()


def register():
    resources = resources_path(sys.argv[1])
    setup = resources / 'setup'
    setup.mkdir(parents=True, exist_ok=True)
    print(f'Using my-resources: {resources}', flush=True)
    # Serialize concurrent registrations, including download and payload activation.
    with (setup / '.exegol-launch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        hook = setup / 'load_user_setup.sh'
        if hook.is_symlink():
            raise ValueError('Setup hook is a symlink; update its target explicitly.')
        old = hook.read_text(encoding='utf-8') if hook.exists() else '#!/bin/bash\n'
        # Collapse complete old managed blocks, even if previous tools duplicated them.
        start, end = '# BEGIN Exegol-launch', '# END Exegol-launch'
        pattern = r'(?ms)^# BEGIN Exegol-launch\n.*?^# END Exegol-launch(?:\n|$)'
        body = re.sub(pattern, '', old)
        if start in body or end in body:
            raise ValueError('Malformed managed block. Repair the hook before registration.')
        if not body.startswith('#!'):
            body = '#!/bin/bash\n' + body
        first, separator, rest = body.partition('\n')
        block = '''# BEGIN Exegol-launch
printf '%s\\n' '[EXEGOL][INFO]Installing Exegol-launch (XFCE Application Finder)'
if bash /opt/my-resources/setup/exegol-launch/install.sh; then
    printf '%s\\n' '[EXEGOL][SUCCESS]Exegol-launch installed; command: launch'
else
    printf '%s\\n' '[EXEGOL][ERROR]Exegol-launch installation failed; inspect /var/log/exegol/load_setups.log(.gz)'
fi
# END Exegol-launch
'''
        updated = first + '\n' + block + rest
        stage = Path(tempfile.mkdtemp(prefix='.launch-stage-', dir=setup))
        target = setup / 'exegol-launch'
        previous = setup / '.exegol-launch.previous'
        temporary_hook = stage / 'hook'
        activated = False
        if previous.exists():
            shutil.rmtree(stage)
            raise ValueError('Interrupted registration found: inspect .exegol-launch.previous before retrying.')
        try:
            source = os.environ.get('EXEGOL_LAUNCH_SOURCE_DIR')
            ref = os.environ.get('EXEGOL_LAUNCH_REF', 'main')
            for name in ('install.sh', 'launch.sh', 'fix-caido.py'):
                if source:
                    content = (Path(source) / name).read_bytes()
                else:
                    url = f'https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/{ref}/{name}'
                    with urllib.request.urlopen(url, timeout=30) as response:
                        content = response.read()
                (stage / name).write_bytes(content)
            for name in ('install.sh', 'launch.sh'):
                subprocess.run(['bash', '-n', str(stage / name)], check=True)
            compile((stage / 'fix-caido.py').read_text(encoding='utf-8'), 'fix-caido.py', 'exec')
            temporary_hook.write_text(updated, encoding='utf-8')
            temporary_hook.chmod((hook.stat().st_mode & 0o777 | 0o100) if hook.exists() else 0o755)
            subprocess.run(['bash', '-n', str(temporary_hook)], check=True)
            # Keep only the first pre-registration backup; repeated runs add no backups.
            backup = setup / 'load_user_setup.sh.exegol-launch.bak'
            if hook.exists() and updated != old and not backup.exists():
                shutil.copy2(hook, backup)
            if target.exists():
                if not (target / '.managed-by-exegol-launch').is_file():
                    raise ValueError(f'Refusing to replace an unrelated directory: {target}')
                target.rename(previous)
            (stage / '.managed-by-exegol-launch').write_text('Exegol-launch\n')
            stage.rename(target)
            activated = True
            (target / 'hook').replace(hook)
        except BaseException:
            if activated:
                shutil.rmtree(target)
            if previous.exists():
                previous.rename(target)
            raise
        finally:
            if stage.exists():
                shutil.rmtree(stage)
        if previous.exists():
            shutil.rmtree(previous)
        # Retire old generated Python payloads, but never arbitrary matching user folders.
        for legacy in setup.glob('.exegol-launch.*'):
            installer = legacy / 'install.sh'
            if legacy.is_dir() and not legacy.is_symlink() and installer.is_file() and (legacy / 'exegol_launch/core.py').is_file():
                if '# Exegol-launch installer:' in installer.read_text(encoding='utf-8'):
                    shutil.rmtree(legacy)
        print(f'Registered: {hook}')
        print('One managed block and one source payload. Existing container installations are unchanged.')
        print('Future containers must mount these resources at /opt/my-resources.')


try:
    register()
except (OSError, ValueError, UnicodeError, subprocess.CalledProcessError) as exc:
    print(f'Exegol-launch registration: {exc}', file=sys.stderr)
    sys.exit(1)
PY
