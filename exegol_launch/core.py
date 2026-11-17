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
    path.mkdir(parents=True, exist_ok=True)
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
        for path in sorted(folder.rglob("*.desktop")):
            ident = str(path.relative_to(folder)).replace("/", "-")
            if ident in seen:
                continue
            # Even a Hidden entry reserves its ID and masks the system version.
            seen.add(ident)
            try:
                parser = configparser.ConfigParser(interpolation=None, strict=False)
                parser.read(path, encoding="utf-8")
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
            except (OSError, ValueError, configparser.Error, KeyError) as exc:
                warnings.append(f"{path}: {exc}")
    # Some Exegol commands have no desktop entry.
    existing = {Path(a.argv[0]).name for a in apps.values()}
    for executable, name in [("burpsuite", "Burp Suite"), ("firefox", "Firefox"), ("wireshark", "Wireshark"), ("zaproxy", "OWASP ZAP"), ("bloodhound", "BloodHound"), ("ghidra", "Ghidra")]:
        if executable not in existing and shutil.which(executable):
            apps["builtin:" + executable] = Application("builtin:" + executable, name, [executable], "Exegol")
    # Custom configuration is optional; report its errors to the GUI.
    path = config_file()
    if path.exists():
        try:
            entries = json.loads(path.read_text())
            if not isinstance(entries, list):
                raise ValueError("apps.json must contain a list")
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError("each application must be an object")
                argv = entry.get("argv")
                if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
                    raise ValueError("argv must be a list of non-empty strings")
                name = entry["name"]
                if not isinstance(name, str) or not name:
                    raise ValueError("name must be a non-empty string")
                ident = "custom:" + name
                apps[ident] = Application(ident, name, argv, str(entry.get("category", "Custom")), bool(entry.get("terminal", False)), entry.get("cwd"), str(entry.get("description", "")))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            warnings.append(f"{path}: {exc}")
    return sorted(apps.values(), key=lambda a: a.name.casefold()), warnings


def launch_app(app: Application) -> Path:
    """Start a detached tool with the current environment and return its log path."""
    argv = list(app.argv)
    if app.terminal:
        terminal = os.environ.get("EXEGOL_LAUNCH_TERMINAL")
        if not terminal:
            terminal = next((x for x in ("x-terminal-emulator", "xterm", "kitty", "alacritty") if shutil.which(x)), None)
        if not terminal:
            raise RuntimeError("No terminal found in the container. Set EXEGOL_LAUNCH_TERMINAL (e.g. 'xterm -e').")
        # Pass arguments directly to the terminal without an implicit shell.
        prefix = shlex.split(terminal)
        if not os.environ.get("EXEGOL_LAUNCH_TERMINAL"):
            prefix.append("-e")
        argv = prefix + argv
    logfile = state_dir() / (re.sub(r"[^a-zA-Z0-9_.-]", "_", app.id) + ".log")
    # Output no longer depends on the terminal or the lifetime of the GUI.
    # Without an env argument, Popen inherits DISPLAY, XAUTHORITY and other variables.
    with logfile.open("ab") as stream:
        # A new session detaches the tool; stdin must not wait on the parent terminal.
        subprocess.Popen(argv, cwd=app.cwd, stdin=subprocess.DEVNULL, stdout=stream, stderr=stream, start_new_session=True, close_fds=True)
    return logfile
