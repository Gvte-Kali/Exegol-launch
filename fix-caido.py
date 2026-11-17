"""Create an explicit root-local Caido override; never alter system desktop entries."""

import os
from pathlib import Path
import re
import shlex
import sys
import tempfile


def fix():
    """Patch only the main Exec field, retaining desktop arguments and metadata."""
    if os.geteuid() != 0:
        raise ValueError('This workaround is only intended for Caido running as root.')
    data_home = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
    roots = [data_home] + [Path(p) for p in os.environ.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':') if p]
    source = next((root / 'applications/caido.desktop' for root in roots if (root / 'applications/caido.desktop').is_file()), None)
    if source is None:
        raise ValueError('caido.desktop was not found. Check the installed Caido desktop-entry filename.')
    text = source.read_text(encoding='utf-8')
    section = None
    found = False
    lines = []
    for line in text.splitlines(keepends=True):
        if line.strip().startswith('['):
            section = line.strip()
        if section == '[Desktop Entry]' and re.match(r'^Exec\s*=', line):
            command = line.split('=', 1)[1].strip()
            argv = shlex.split(command)
            if not argv or Path(argv[0]).name.lower() not in ('caido', 'caido-desktop'):
                raise ValueError('Unexpected Caido Exec command; edit this entry manually rather than patching a wrapper.')
            if '--no-sandbox' not in argv:
                line = line.rstrip('\r\n') + ' --no-sandbox\n'
            found = True
        lines.append(line)
    if not found:
        raise ValueError('The Caido desktop entry has no main Exec field.')
    destination = data_home / 'applications/caido.desktop'
    destination.parent.mkdir(parents=True, exist_ok=True)
    updated = ''.join(lines)
    if destination.exists() and destination.read_text(encoding='utf-8') == updated:
        print(f'Caido override already configured: {destination}')
        return
    # Preserve the first user entry once, not one backup per invocation.
    backup = destination.with_suffix('.desktop.exegol-launch.bak')
    if destination.exists() and not backup.exists():
        backup.write_bytes(destination.read_bytes())
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=destination.parent, prefix='.caido-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(updated)
        temporary.chmod(0o644)
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f'Created {destination}. Caido will run with --no-sandbox for this user.')
    print('This disables Electron sandboxing for Caido. Restart Application Finder to reload entries.')


if __name__ == '__main__':
    try:
        fix()
    except (OSError, ValueError, UnicodeError) as exc:
        print(f'Caido override: {exc}', file=sys.stderr)
        sys.exit(1)
