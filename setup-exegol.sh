#!/usr/bin/env bash
# Run on the HOST, as the user who runs Exegol (no sudo).
set -euo pipefail
resources="${1:-${EXEGOL_MY_RESOURCES:-$HOME/.exegol/my-resources}}"
ref="${EXEGOL_LAUNCH_REF:-main}"
base="https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/$ref"
command -v python3 >/dev/null || { echo 'Python 3 requis sur l’hôte.' >&2; exit 1; }
mkdir -p "$resources/setup"
# Resolve the host path before writing; the hook uses Exegol's container mount path.
resources="$(cd -- "$resources" && pwd)"
stage="$(mktemp -d "$resources/setup/.exegol-launch.XXXXXXXX")"
trap 'rm -rf -- "$stage"' EXIT
mkdir -p "$stage/exegol_launch"
for file in install.sh exegol_launch/__init__.py exegol_launch/__main__.py exegol_launch/core.py exegol_launch/cli.py exegol_launch/gui.py; do
    if [[ -n "${EXEGOL_LAUNCH_SOURCE_DIR:-}" ]]; then
        cp -- "$EXEGOL_LAUNCH_SOURCE_DIR/$file" "$stage/$file"
    else
        curl --fail --silent --show-error --location "$base/$file" -o "$stage/$file"
    fi
done
python3 -m compileall -q "$stage/exegol_launch"
# Versioned payload: hook update is atomic, previous payloads remain available.
payload="$(basename "$stage")"
python3 - "$resources/setup/load_user_setup.sh" "$payload" <<'PY'
from pathlib import Path
import os, re, shutil, sys
path = Path(sys.argv[1])
payload = sys.argv[2]
if path.is_symlink():
    raise SystemExit('Le hook est un lien symbolique : adapte-le manuellement pour conserver sa cible.')
old = path.read_text() if path.exists() else '#!/bin/bash\n'
start, end = '# BEGIN Exegol-launch', '# END Exegol-launch'
if old.count(start) != old.count(end) or old.count(start) > 1:
    raise SystemExit('Bloc Exegol-launch mal formé : corrige le hook avant de continuer.')
body = re.sub(r'(?ms)^# BEGIN Exegol-launch\n.*?^# END Exegol-launch\n?', '', old)
# Insert before existing code (including a possible exit/return), after its shebang.
lines = body.splitlines(keepends=True)
index = 1 if lines and lines[0].startswith('#!') else 0
block = f'''# BEGIN Exegol-launch
# Local payload shared by Exegol; apt may need network if Tkinter is absent.
if ! bash /opt/my-resources/setup/{payload}/install.sh; then
    printf '%s\\n' '[Exegol-launch] Installation échouée ; voir les logs de création.' >&2
fi
# END Exegol-launch
'''
if index and not lines[0].endswith('\n'):
    lines[0] += '\n'
lines.insert(index, block)
if path.exists():
    backup = path.with_name(path.name + '.bak-' + str(__import__('time').time_ns()))
    shutil.copy2(path, backup)
    print(f'Sauvegarde : {backup}')
tmp = path.with_name('.load_user_setup-' + str(os.getpid()))
tmp.write_text(''.join(lines))
tmp.chmod(path.stat().st_mode & 0o777 if path.exists() else 0o755)
os.replace(tmp, path)
PY
# Do not remove the payload now referenced by the hook.
trap - EXIT
printf 'Enregistré dans %s/setup/load_user_setup.sh\n' "$resources"
printf 'Les futurs conteneurs avec my-resources activé installeront launch au premier démarrage.\n'
