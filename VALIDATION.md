# Version 0.1.0 validation

- Six engine and installer tests pass without a graphical display.
- Tests cover XDG discovery, desktop arguments, inherited environment and detached child processes.
- Installation, updates, command collisions, idempotent hook registration and backups are checked in temporary directories.
- GUI appearance and Exegol/host graphical integration require manual validation with a real display.

## Manual integration checklist

1. Run `launch` from a container terminal with working graphical access; confirm the prompt returns.
2. Select an installed GUI application and confirm its window opens on the intended display.
3. Close the launcher and confirm the application remains running.
4. Reopen the launcher and check search and favorite persistence.
5. If an application fails, use `launch --foreground` and inspect its log.
