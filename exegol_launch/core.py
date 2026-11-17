"""Tkinter-independent engine for application discovery, configuration and launching."""

from __future__ import annotations

import configparser
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class Application:
    """Shared model for desktop entries, detected tools and custom commands."""
    id: str
    name: str
    argv: list[str]
    category: str = "Other"
    terminal: bool = False
    cwd: str | None = None
    description: str = ""


def state_dir() -> Path:
    """Create and return the XDG directory for logs and favorites."""
    path = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "exegol-launch"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OSError(f"Cannot create state directory {path}: {exc}") from exc
    return path


def config_file() -> Path:
    """Return the XDG custom-command configuration path without creating it."""
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "exegol-launch/apps.json"


def expand_exec(command: str, name: str, desktop: str, icon: str = "") -> list[str]:
    """Parse Exec arguments and expand desktop field codes without invoking a shell."""
    result = []
    for token in shlex.split(command):
        if token == "%i":
            if icon:
                result.extend(["--icon", icon])
        elif token == "%c":
            result.append(name)
        elif token == "%k":
            result.append(desktop)
        else:
            # File/URL placeholders have no value when launched without a document.
            token = token.replace("%%", "\0")
            token = re.sub(r"%[A-Za-z]", "", token).replace("\0", "%")
            if token:
                result.append(token)
    return result


def discover() -> tuple[list[Application], list[str]]:
    """Merge XDG entries, known tools and JSON commands, returning warnings alongside apps."""
    apps, warnings, seen = {}, [], set()
    # Order matters: user entries override system entries.
    roots = [Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))]
    roots += [Path(p) for p in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":") if p]
    for root in roots:
        folder = root / "applications"
        if not folder.is_dir():
            continue
        try:
            desktop_files = sorted(folder.rglob("*.desktop"))
        except OSError as exc:
            warnings.append(f"Cannot scan {folder}: {exc}")
            continue
        for path in desktop_files:
            ident = str(path.relative_to(folder)).replace("/", "-")
            if ident in seen:
                continue
            # Even a Hidden entry reserves its ID and masks the system version.
            seen.add(ident)
            try:
                parser = configparser.ConfigParser(interpolation=None, strict=False)
                # Opening explicitly reports unreadable files instead of silently ignoring them.
                with path.open(encoding="utf-8") as stream:
                    parser.read_file(stream)
                entry = parser["Desktop Entry"]
                if entry.get("Type", "Application") != "Application" or any(entry.getboolean(k, fallback=False) for k in ("Hidden", "NoDisplay")):
                    continue
                name = entry.get("Name", path.stem)
                argv = expand_exec(entry.get("Exec", ""), name, str(path), entry.get("Icon", ""))
                # TryExec lets the desktop entry declare its actual executable requirement.
                probe = entry.get("TryExec") or (argv[0] if argv else "")
                if not argv or not shutil.which(probe):
                    continue
                categories = entry.get("Categories", "").strip(";").split(";")
                apps[ident] = Application(ident, name, argv, categories[0] or "Other", entry.getboolean("Terminal", fallback=False), entry.get("Path") or None, entry.get("Comment", ""))
            except (OSError, ValueError, UnicodeError, configparser.Error, KeyError) as exc:
                warnings.append(f"{path}: {exc}")
    # Some Exegol commands have no desktop entry.
    existing = {Path(a.argv[0]).name for a in apps.values()}
    for executable, name in [("burpsuite", "Burp Suite"), ("firefox", "Firefox"), ("wireshark", "Wireshark"), ("zaproxy", "OWASP ZAP"), ("bloodhound", "BloodHound"), ("ghidra", "Ghidra")]:
        if executable not in existing and shutil.which(executable):
            apps["builtin:" + executable] = Application("builtin:" + executable, name, [executable], "Exegol")
    # Custom configuration is optional; report its errors to the GUI.
    path = config_file()
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(entries, list):
            raise ValueError("apps.json must contain a list")
    except FileNotFoundError:
        entries = []
    except (OSError, ValueError, UnicodeError) as exc:
        warnings.append(f"{path}: {exc}")
        entries = []
    for index, entry in enumerate(entries, start=1):
        # One malformed command must not hide the remaining valid entries.
        try:
            if not isinstance(entry, dict):
                raise ValueError("each application must be an object")
            argv = entry.get("argv")
            if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x and "\0" not in x for x in argv):
                raise ValueError("argv must be a list of non-empty strings without NUL characters")
            name = entry.get("name")
            if not isinstance(name, str) or not name.strip() or "\0" in name:
                raise ValueError("name must be a non-empty string without NUL characters")
            terminal = entry.get("terminal", False)
            if not isinstance(terminal, bool):
                raise ValueError("terminal must be a JSON boolean (true or false)")
            cwd = entry.get("cwd")
            if cwd is not None and (not isinstance(cwd, str) or not cwd or "\0" in cwd):
                raise ValueError("cwd must be a non-empty path string")
            for key in ("category", "description"):
                if key in entry and not isinstance(entry[key], str):
                    raise ValueError(f"{key} must be a string")
            ident = "custom:" + name
            if ident in apps:
                raise ValueError(f"duplicate custom application name: {name}")
            apps[ident] = Application(ident, name, argv, entry.get("category", "Custom"), terminal, cwd, entry.get("description", ""))
        except (ValueError, TypeError) as exc:
            warnings.append(f"{path}, entry {index}: {exc}")
    return sorted(apps.values(), key=lambda a: a.name.casefold()), warnings


def launch_app(app: Application, *, on_started=None) -> Path:
    """Start a detached tool with the current environment and return its log path."""
    if not isinstance(app.argv, list) or not app.argv or not all(isinstance(arg, str) and arg and "\0" not in arg for arg in app.argv):
        raise ValueError("Application arguments must be non-empty strings without NUL characters")
    if app.cwd is not None and not Path(app.cwd).is_dir():
        raise ValueError(f"Working directory does not exist or is not a directory: {app.cwd}")
    argv = list(app.argv)
    if app.terminal:
        terminal = os.environ.get("EXEGOL_LAUNCH_TERMINAL")
        if not terminal:
            terminal = next((x for x in ("x-terminal-emulator", "xterm", "kitty", "alacritty") if shutil.which(x)), None)
        if not terminal:
            raise RuntimeError("No terminal found in the container. Set EXEGOL_LAUNCH_TERMINAL (e.g. 'xterm -e').")
        # Pass arguments directly to the terminal without an implicit shell.
        try:
            prefix = shlex.split(terminal)
        except ValueError as exc:
            raise ValueError(f"Invalid EXEGOL_LAUNCH_TERMINAL: {exc}") from exc
        if not prefix or not shutil.which(prefix[0]):
            raise ValueError("EXEGOL_LAUNCH_TERMINAL must start with an available executable")
        if not os.environ.get("EXEGOL_LAUNCH_TERMINAL"):
            prefix.append("-e")
        argv = prefix + argv
    # Bound the filename length and hash the ID to avoid sanitized-name collisions.
    import hashlib
    safe_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", app.id)[:100]
    digest = hashlib.sha256(app.id.encode("utf-8")).hexdigest()[:12]
    logfile = state_dir() / f"{safe_id}-{digest}.log"
    # Output no longer depends on the terminal or the lifetime of the GUI.
    # Without an env argument, Popen inherits DISPLAY, XAUTHORITY and other variables.
    with logfile.open("ab") as stream:
        # A new session detaches the tool; stdin must not wait on the parent terminal.
        try:
            process = subprocess.Popen(argv, cwd=app.cwd, stdin=subprocess.DEVNULL, stdout=stream, stderr=stream, start_new_session=True, close_fds=True)
        except OSError as exc:
            raise OSError(f"Unable to start {app.name}: {exc}. Log: {logfile}") from exc
    if on_started is not None:
        on_started(process, logfile)
    return logfile
