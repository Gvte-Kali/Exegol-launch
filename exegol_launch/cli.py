import argparse
import os
from pathlib import Path
import subprocess
import sys
from .core import discover, state_dir


def main():
    parser = argparse.ArgumentParser(description="Exegol-launch — lanceur graphique dans Exegol")
    parser.add_argument("--foreground", action="store_true", help="Garder le launcher au premier plan pour diagnostic")
    parser.add_argument("--list", action="store_true", help="Lister les applications sans GUI")
    parser.add_argument("--version", action="version", version="Exegol-launch 0.1.0")
    args = parser.parse_args()
    if args.list:
        apps, warnings = discover()
        for app in apps:
            print(f"{app.name}\t{app.category}\t{app.argv!r}")
        for warning in warnings:
            print(warning, file=sys.stderr)
        return
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        parser.exit(1, "Aucun affichage graphique. Lance launch depuis le terminal Exegol où burpsuite fonctionne.\n")
    try:
        import tkinter as tk
    except ImportError:
        parser.exit(1, "Tkinter absent. Dans Exegol : apt update && apt install python3-tk\n")
    if args.foreground:
        from .gui import run
        try:
            run()
        except tk.TclError as exc:
            parser.exit(1, f"Impossible d'ouvrir la fenêtre : {exc}\nVérifie DISPLAY et les autorisations graphiques du conteneur.\n")
        return
    # Check the display before detaching so errors remain visible in the terminal.
    try:
        root = tk.Tk()
        root.withdraw()
        root.destroy()
    except tk.TclError as exc:
        parser.exit(1, f"Affichage inaccessible : {exc}\n")
    logfile = state_dir() / "launcher.log"
    with logfile.open("ab") as stream:
        subprocess.Popen([sys.executable, "-m", "exegol_launch", "--foreground"], stdin=subprocess.DEVNULL, stdout=stream, stderr=stream, start_new_session=True, close_fds=True)
    print(f"Exegol-launch démarré · journal : {logfile}")
