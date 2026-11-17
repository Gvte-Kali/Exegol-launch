"""CLI entry point; defer GUI imports so --list works without a display."""

import argparse
import os
import subprocess
import sys
from .core import discover, state_dir


def _main():
    """Handle CLI options and open the GUI directly or in a detached process."""
    parser = argparse.ArgumentParser(description="Exegol-launch — graphical application launcher for Exegol")
    parser.add_argument("--foreground", action="store_true", help="Run the launcher in the foreground for diagnostics")
    parser.add_argument("--list", action="store_true", help="List applications without opening the GUI")
    parser.add_argument("--version", action="version", version="Exegol-launch 0.1.0")
    args = parser.parse_args()
    # Text mode supports tests and containers without a graphical display.
    if args.list:
        apps, warnings = discover()
        for app in apps:
            print(f"{app.name}\t{app.category}\t{app.argv!r}")
        for warning in warnings:
            print(warning, file=sys.stderr)
        return
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        parser.exit(1, "No graphical display found. Run launch from an Exegol terminal with working graphical access.\n")
    try:
        import tkinter as tk
    except ImportError:
        parser.exit(1, "Tkinter is missing. In Exegol, run: apt update && apt install python3-tk\n")
    # The child process created in normal mode also uses this path.
    if args.foreground:
        from .gui import run
        try:
            run()
        except tk.TclError as exc:
            parser.exit(1, f"Unable to open the window: {exc}\nCheck DISPLAY and the container's graphical access permissions.\n")
        return
    # Check the display before detaching so errors remain visible in the terminal.
    try:
        root = tk.Tk()
        root.withdraw()
        root.destroy()
    except tk.TclError as exc:
        parser.exit(1, f"Display is inaccessible: {exc}\n")
    # Reuse this interpreter to avoid switching Python installations after detaching.
    logfile = state_dir() / "launcher.log"
    with logfile.open("ab") as stream:
        child = subprocess.Popen([sys.executable, "-m", "exegol_launch", "--foreground"], stdin=subprocess.DEVNULL, stdout=stream, stderr=stream, start_new_session=True, close_fds=True)
    # Surface immediate startup failures instead of reporting an unconditional success.
    try:
        code = child.wait(timeout=0.3)
    except subprocess.TimeoutExpired:
        pass
    else:
        if code:
            parser.exit(1, f"Launcher exited with status {code}. See {logfile} or use --foreground.\n")
        return
    print(f"Exegol-launch started · log: {logfile}")


def main():
    """Keep expected operational failures readable, with meaningful exit codes."""
    try:
        _main()
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Exegol-launch: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
