#!/usr/bin/env bash
# Run on the HOST, as the user who runs Exegol (no sudo).
set -Eeuo pipefail
# ERR reports the failing step; EXIT still cleans incomplete staging directories.
trap 'code=$?; printf "Exegol-launch: %s failed at line %s (status %s).\n" "${BASH_SOURCE[0]:-installer}" "$LINENO" "$code" >&2; exit "$code"' ERR
# Avoid indefinite hangs when GitHub or a proxy is unavailable.
download() {
    command -v curl >/dev/null || { echo 'curl is required for remote installation.' >&2; return 1; }
    curl --fail --silent --show-error --location --connect-timeout 10 --max-time 120 --retry 2 "$@"
}
# The first argument supports a custom my_resources_path.
resources="${1:-${EXEGOL_MY_RESOURCES:-$HOME/.exegol/my-resources}}"
ref="${EXEGOL_LAUNCH_REF:-main}"
base="https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/$ref"
command -v python3 >/dev/null || { echo 'Python 3 is required on the host.' >&2; exit 1; }
mkdir -p "$resources/setup"
# Resolve the host path before writing; the hook uses Exegol's container mount path.
resources="$(cd -- "$resources" && pwd)"
stage="$(mktemp -d "$resources/setup/.exegol-launch.XXXXXXXX")"
trap 'rm -rf -- "$stage"' EXIT
mkdir -p "$stage/exegol_launch"
# Explicit distribution list: excludes tests and development tools.
for file in install.sh exegol_launch/__init__.py exegol_launch/__main__.py exegol_launch/core.py exegol_launch/cli.py exegol_launch/gui.py; do
    if [[ -n "${EXEGOL_LAUNCH_SOURCE_DIR:-}" ]]; then
        cp -- "$EXEGOL_LAUNCH_SOURCE_DIR/$file" "$stage/$file"
    else
        download "$base/$file" -o "$stage/$file"
    fi
done
bash -n "$stage/install.sh"
python3 -m compileall -q "$stage/exegol_launch"
# Versioned payload: hook update is atomic, previous payloads remain available.
payload="$(basename "$stage")"
python3 - "$resources/setup/load_user_setup.sh" "$payload" <<'PY'
from pathlib import Path
import os, re, shutil, sys
path = Path(sys.argv[1])
payload = sys.argv[2]
if path.is_symlink():
    raise SystemExit('The hook is a symlink: update it manually to preserve its target.')
# Preserve existing customizations; create a shebang if the hook is missing.
old = path.read_text() if path.exists() else '#!/bin/bash\n'
start, end = '# BEGIN Exegol-launch', '# END Exegol-launch'
if old.count(start) != old.count(end) or old.count(start) > 1:
    raise SystemExit('Malformed Exegol-launch block: fix the hook before continuing.')
# Remove only our previous block; leave other tools unchanged.
body = re.sub(r'(?ms)^# BEGIN Exegol-launch\n.*?^# END Exegol-launch\n?', '', old)
# Insert before existing code (including a possible exit/return), after its shebang.
lines = body.splitlines(keepends=True)
index = 1 if lines and lines[0].startswith('#!') else 0
block = f'''# BEGIN Exegol-launch
# Exegol only forwards lines with its tagged logging prefix to the host terminal.
printf '%s\\n' '[EXEGOL][INFO]Installing Exegol-launch'
if bash /opt/my-resources/setup/{payload}/install.sh; then
    printf '%s\\n' '[EXEGOL][SUCCESS]Exegol-launch installed; command: launch'
else
    printf '%s\\n' '[EXEGOL][ERROR]Exegol-launch installation failed. Inspect /var/log/exegol/load_setups.log(.gz) inside the container.' >&2
fi
# END Exegol-launch
'''
if index and not lines[0].endswith('\n'):
    lines[0] += '\n'
lines.insert(index, block)
# Create a separate backup on each registration.
if path.exists():
    backup = path.with_name(path.name + '.bak-' + str(__import__('time').time_ns()))
    shutil.copy2(path, backup)
    print(f'Backup: {backup}')
tmp = path.with_name('.load_user_setup-' + str(os.getpid()))
tmp.write_text(''.join(lines), encoding='utf-8')
# Exegol executes this file directly, rather than passing it to bash.
# Preserve existing permissions, but ensure the owner can execute the hook.
tmp.chmod((path.stat().st_mode & 0o777 | 0o100) if path.exists() else 0o755)
# Replace the hook in one operation; its referenced payload is already complete.
# Validate the complete hook, including pre-existing code, before activation.
import subprocess
try:
    subprocess.run(['bash', '-n', str(tmp)], check=True)
    os.replace(tmp, path)
finally:
    tmp.unlink(missing_ok=True)
PY
# Do not remove the payload now referenced by the hook.
trap - EXIT
printf 'Registered in %s/setup/load_user_setup.sh\n' "$resources"
printf 'Future containers with my-resources enabled will install launch on first startup.\n'
