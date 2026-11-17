#!/usr/bin/env bash
# Exegol-launch installer: install a native XFCE wrapper, without Tkinter or pip.
set -Eeuo pipefail
trap 'code=$?; printf "Exegol-launch install failed at line %s (status %s).\n" "$LINENO" "$code" >&2; exit "$code"' ERR
ref="${EXEGOL_LAUNCH_REF:-main}"
base="https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/$ref"
if [[ $EUID -eq 0 ]]; then default_home=/opt/exegol-launch; default_bin=/usr/local/bin
else default_home="${XDG_DATA_HOME:-$HOME/.local/share}/exegol-launch"; default_bin="$HOME/.local/bin"; fi
install_dir="${EXEGOL_LAUNCH_HOME:-$default_home}"
bin_dir="${EXEGOL_LAUNCH_BIN:-$default_bin}"
source_dir="${EXEGOL_LAUNCH_SOURCE_DIR:-}"
if [[ -z "$source_dir" && -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
    candidate="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
    [[ ! -f "$candidate/launch.sh" ]] || source_dir="$candidate"
fi
mkdir -p -- "$install_dir" "$bin_dir"
install_dir="$(cd -- "$install_dir" && pwd)"
bin_dir="$(cd -- "$bin_dir" && pwd)"
command -v flock >/dev/null || { echo 'flock is required (util-linux).' >&2; exit 1; }
exec 9>"$install_dir/.install.lock"
flock -x 9
if [[ -e "$bin_dir/launch" || -L "$bin_dir/launch" ]]; then
    grep -q '^# Managed by Exegol-launch$' "$bin_dir/launch" || {
        echo "Refusing to overwrite unrelated command: $bin_dir/launch" >&2; exit 1;
    }
fi
if ! command -v xfce4-appfinder >/dev/null; then
    if [[ $EUID -ne 0 ]] || ! command -v apt-get >/dev/null; then
        echo 'Install xfce4-appfinder manually, then retry.' >&2; exit 1
    fi
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y xfce4-appfinder
fi
command -v setsid >/dev/null || { echo 'setsid is required (util-linux).' >&2; exit 1; }
stage="$(mktemp -d "$install_dir/.staging.XXXXXXXX")"
trap 'rm -rf -- "$stage"' EXIT
for file in launch.sh fix-caido.py; do
    if [[ -n "$source_dir" ]]; then cp -- "$source_dir/$file" "$stage/$file"
    else curl -fsSL --connect-timeout 10 --max-time 120 --retry 2 "$base/$file" -o "$stage/$file"; fi
done
bash -n "$stage/launch.sh"
chmod 755 "$stage/launch.sh"
# A stable symlink keeps a real command in PATH, without adding shell aliases.
# Keep the old payload until both the directory and command have been activated.
if [[ -e "$install_dir/native.previous" ]]; then echo 'Interrupted update found: inspect native.previous before retrying.' >&2; exit 1; fi
if [[ -e "$install_dir/native" ]]; then mv -- "$install_dir/native" "$install_dir/native.previous"; fi
if mv -- "$stage" "$install_dir/native" && ln -sfn -- "$install_dir/native/launch.sh" "$bin_dir/.launch-new" && mv -Tf -- "$bin_dir/.launch-new" "$bin_dir/launch"; then
    rm -rf -- "$install_dir/native.previous"
else
    rm -f -- "$bin_dir/.launch-new"
    rm -rf -- "$install_dir/native"
    if [[ -d "$install_dir/native.previous" ]]; then mv -- "$install_dir/native.previous" "$install_dir/native"; fi
    echo 'Activation failed; previous native payload restored.' >&2; exit 1
fi
# Remove the previous managed Python implementation when migrating from 0.1.
if [[ -L "$install_dir/current" && -d "$install_dir/releases" ]]; then
    rm -f -- "$install_dir/current"
    rm -rf -- "$install_dir/releases"
fi
printf 'Exegol-launch installed: %s/launch\n' "$bin_dir"
printf 'Uses XFCE Application Finder; no Tkinter required. Run: launch\n'
