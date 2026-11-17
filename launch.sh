#!/usr/bin/env bash
# Managed by Exegol-launch
# Keep the container's display environment; never reuse XFCE's existing D-Bus service.
set -Eeuo pipefail
case "${1:-}" in
    --version) echo 'Exegol-launch 0.2.0 (XFCE Application Finder)'; exit 0 ;;
    --help|-h)
        printf '%s\n' 'Usage: launch [--foreground | --fix-caido | APPFINDER_OPTIONS]' \
            'Open XFCE Application Finder on the display inherited from this terminal.' \
            '--foreground  Keep diagnostic output in the terminal.' \
            '--fix-caido   Create a root-only local Caido desktop override with --no-sandbox.'
        exit 0 ;;
    --fix-caido)
        command -v python3 >/dev/null || { echo 'Python 3 is required to edit the Caido entry.' >&2; exit 1; }
        exec python3 "$(dirname -- "$(readlink -f -- "$0")")/fix-caido.py" ;;
esac
command -v xfce4-appfinder >/dev/null || { echo 'xfce4-appfinder is missing. Re-run the installer inside the container.' >&2; exit 1; }
if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    echo 'No display configured. Use a container terminal with working graphical access.' >&2
    exit 1
fi
# --disable-server forces a fresh process, using this terminal's display rather than VNC's.
if [[ "${1:-}" == --foreground ]]; then
    shift
    exec xfce4-appfinder --disable-server "$@"
fi
command -v setsid >/dev/null || { echo 'setsid is required (util-linux).' >&2; exit 1; }
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/exegol-launch"
mkdir -p -- "$state_dir" || { echo "Cannot create log directory: $state_dir" >&2; exit 1; }
log="$state_dir/appfinder.log"
# nohup protects against shell hangup; setsid separates the session; all streams are detached.
nohup setsid xfce4-appfinder --disable-server "$@" </dev/null >>"$log" 2>&1 &
pid=$!
# Detect immediate startup failure; later failures remain available in the log.
sleep 0.2
if ! kill -0 "$pid" 2>/dev/null; then
    if wait "$pid"; then exit 0; else
        code=$?
        printf 'Application Finder exited with status %s. Log: %s\n' "$code" "$log" >&2
        exit "$code"
    fi
fi
printf 'Application Finder started. Log: %s\n' "$log"
