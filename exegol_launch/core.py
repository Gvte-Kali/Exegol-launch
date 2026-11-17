"""Moteur indépendant de Tkinter : découverte, configuration et lancement des outils."""

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
    """Description commune à une entrée .desktop, un outil détecté ou une commande utilisateur."""
    id: str
    name: str
    argv: list[str]
    category: str = "Autres"
    terminal: bool = False
    cwd: str | None = None
    description: str = ""


def state_dir() -> Path:
    """Créer le dossier XDG des journaux et favoris, puis retourner son chemin."""
    path = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "exegol-launch"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_file() -> Path:
    """Retourner le chemin XDG du fichier de commandes personnalisées sans le créer."""
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "exegol-launch/apps.json"


def expand_exec(command: str, name: str, desktop: str, icon: str = "") -> list[str]:
    """Convertir Exec en arguments, en remplaçant les codes desktop sans passer par un shell."""
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
    """Fusionner entrées XDG, outils connus et commandes JSON ; retourner aussi les avertissements."""
    apps, warnings, seen = {}, [], set()
    # L’ordre est important : les entrées utilisateur remplacent celles du système.
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
            # Même une entrée Hidden réserve son identifiant et masque la version système.
            seen.add(ident)
            try:
                parser = configparser.ConfigParser(interpolation=None, strict=False)
                parser.read(path, encoding="utf-8")
                entry = parser["Desktop Entry"]
                if entry.get("Type", "Application") != "Application" or any(entry.getboolean(k, fallback=False) for k in ("Hidden", "NoDisplay")):
                    continue
                name = entry.get("Name", path.stem)
                argv = expand_exec(entry.get("Exec", ""), name, str(path), entry.get("Icon", ""))
                # TryExec permet au fichier desktop de déclarer son véritable prérequis.
                probe = entry.get("TryExec") or (argv[0] if argv else "")
                if not argv or not shutil.which(probe):
                    continue
                categories = entry.get("Categories", "").strip(";").split(";")
                apps[ident] = Application(ident, name, argv, categories[0] or "Autres", entry.getboolean("Terminal", fallback=False), entry.get("Path") or None, entry.get("Comment", ""))
            except (OSError, ValueError, configparser.Error, KeyError) as exc:
                warnings.append(f"{path}: {exc}")
    # Some Exegol commands have no desktop entry.
    existing = {Path(a.argv[0]).name for a in apps.values()}
    for executable, name in [("burpsuite", "Burp Suite"), ("firefox", "Firefox"), ("wireshark", "Wireshark"), ("zaproxy", "OWASP ZAP"), ("bloodhound", "BloodHound"), ("ghidra", "Ghidra")]:
        if executable not in existing and shutil.which(executable):
            apps["builtin:" + executable] = Application("builtin:" + executable, name, [executable], "Exegol")
    # La configuration personnalisée est optionnelle ; ses erreurs remontent à la GUI.
    path = config_file()
    if path.exists():
        try:
            entries = json.loads(path.read_text())
            if not isinstance(entries, list):
                raise ValueError("apps.json doit contenir une liste")
            for entry in entries:
                if not isinstance(entry, dict):
                    raise ValueError("chaque application doit être un objet")
                argv = entry.get("argv")
                if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
                    raise ValueError("argv doit être une liste de chaînes non vides")
                name = entry["name"]
                if not isinstance(name, str) or not name:
                    raise ValueError("name doit être une chaîne non vide")
                ident = "custom:" + name
                apps[ident] = Application(ident, name, argv, str(entry.get("category", "Personnel")), bool(entry.get("terminal", False)), entry.get("cwd"), str(entry.get("description", "")))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            warnings.append(f"{path}: {exc}")
    return sorted(apps.values(), key=lambda a: a.name.casefold()), warnings


def launch_app(app: Application) -> Path:
    """Démarrer un outil détaché avec l’environnement courant et retourner le chemin de son journal."""
    argv = list(app.argv)
    if app.terminal:
        terminal = os.environ.get("EXEGOL_LAUNCH_TERMINAL")
        if not terminal:
            terminal = next((x for x in ("x-terminal-emulator", "xterm", "kitty", "alacritty") if shutil.which(x)), None)
        if not terminal:
            raise RuntimeError("Aucun terminal dans le conteneur. Définis EXEGOL_LAUNCH_TERMINAL (ex. 'xterm -e').")
        # Le terminal reçoit les arguments directement : aucun shell implicite.
        prefix = shlex.split(terminal)
        if not os.environ.get("EXEGOL_LAUNCH_TERMINAL"):
            prefix.append("-e")
        argv = prefix + argv
    logfile = state_dir() / (re.sub(r"[^a-zA-Z0-9_.-]", "_", app.id) + ".log")
    # Les sorties ne dépendent plus du terminal ni de la durée de vie de la GUI.
    # Sans argument env, Popen hérite notamment de DISPLAY et XAUTHORITY.
    with logfile.open("ab") as stream:
        # Une nouvelle session détache l’outil ; stdin ne doit pas attendre le terminal parent.
        subprocess.Popen(argv, cwd=app.cwd, stdin=subprocess.DEVNULL, stdout=stream, stderr=stream, start_new_session=True, close_fds=True)
    return logfile
