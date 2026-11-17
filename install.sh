#!/usr/bin/env bash
# Exegol-launch installer: local checkout or curl .../install.sh | bash
set -euo pipefail
# La même référence sert à tous les fichiers distants ; un SHA permet de figer la version.
repo='Gvte-Kali/Exegol-launch'
ref="${EXEGOL_LAUNCH_REF:-main}"
base="https://raw.githubusercontent.com/$repo/$ref"
# Root installe pour tous les utilisateurs du conteneur ; sinon utiliser les dossiers personnels.
if [[ $EUID -eq 0 ]]; then
    default_home=/opt/exegol-launch
    default_bin=/usr/local/bin
else
    default_home="${XDG_DATA_HOME:-$HOME/.local/share}/exegol-launch"
    default_bin="$HOME/.local/bin"
fi
install_dir="${EXEGOL_LAUNCH_HOME:-$default_home}"
bin_dir="${EXEGOL_LAUNCH_BIN:-$default_bin}"
source_dir="${EXEGOL_LAUNCH_SOURCE_DIR:-}"
# Un clone local ou un payload my-resources évite les téléchargements GitHub.
if [[ -z "$source_dir" && -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
    candidate="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
    [[ ! -f "$candidate/exegol_launch/core.py" ]] || source_dir="$candidate"
fi
# Le marqueur distingue notre wrapper d’une commande homonyme appartenant à un autre outil.
if [[ -e "$bin_dir/launch" || -L "$bin_dir/launch" ]]; then
    grep -q '^# Managed by Exegol-launch$' "$bin_dir/launch" || {
        echo "Refus d'écraser la commande existante : $bin_dir/launch" >&2; exit 1;
    }
fi
# Prefer system Python, since pyenv Python may lack the distro's Tkinter.
python_bin=""
for candidate in /usr/bin/python3 "$(command -v python3 || true)"; do
    if [[ -x "$candidate" ]] && "$candidate" -c 'import sys, tkinter; assert sys.version_info >= (3,10)' 2>/dev/null; then
        python_bin="$candidate"; break
    fi
done
# Installer uniquement les dépendances absentes ; les échecs apt restent visibles.
if [[ -z "$python_bin" ]]; then
    if [[ $EUID -ne 0 ]] || ! command -v apt-get >/dev/null; then
        echo 'Python 3.10+ et Tkinter requis. Dans Exegol : apt update && apt install python3 python3-tk' >&2
        exit 1
    fi
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-tk
    python_bin=/usr/bin/python3
    "$python_bin" -c 'import sys, tkinter; assert sys.version_info >= (3,10)'
fi
mkdir -p "$install_dir/releases" "$bin_dir"
# Stage all files before activating a release; a failed download keeps the old version.
stage="$(mktemp -d "$install_dir/releases/release.XXXXXXXX")"
# Tant que stage est défini, toute sortie supprime la release incomplète.
cleanup() { [[ -z "${stage:-}" ]] || rm -rf -- "$stage"; }
trap cleanup EXIT
mkdir -p "$stage/exegol_launch"
for file in __init__.py __main__.py core.py cli.py gui.py; do
    if [[ -n "$source_dir" ]]; then
        cp -- "$source_dir/exegol_launch/$file" "$stage/exegol_launch/$file"
    else
        curl --fail --silent --show-error --location "$base/exegol_launch/$file" -o "$stage/exegol_launch/$file"
    fi
done
# Valider la syntaxe avant de modifier le lien utilisé par la commande launch.
"$python_bin" -m compileall -q "$stage/exegol_launch"
"$python_bin" - "$install_dir" "$bin_dir/launch" "$python_bin" "$stage" <<'PY'
import os, pathlib, shlex, sys
base, wrapper, python, release = sys.argv[1:]
base = pathlib.Path(base).resolve()
# Le lien current fournit un point d’activation stable pour toutes les releases.
current = base / 'current'
if current.exists() and not current.is_symlink():
    raise SystemExit(f'Refus de remplacer un dossier non géré : {current}')
link = base / ('.current-' + str(os.getpid()))
link.symlink_to(pathlib.Path(release).resolve())
# Le remplacement du lien est atomique sur le même système de fichiers.
os.replace(link, current)
p = pathlib.Path(wrapper)
tmp = p.with_name('.launch-' + str(os.getpid()))
# shlex.quote protège les chemins contenant espaces ou caractères spéciaux.
tmp.write_text('#!/bin/sh\n# Managed by Exegol-launch\nPYTHONPATH=' + shlex.quote(str(current)) + ' exec ' + shlex.quote(python) + ' -m exegol_launch "$@"\n')
tmp.chmod(0o755)
os.replace(tmp, p)
PY
# La release est active : désarmer sa suppression par le trap EXIT.
stage=''
printf 'Exegol-launch installé : %s/launch\nLance : launch\n' "$bin_dir"
printf 'Ajoute %s au PATH si nécessaire. Les anciennes releases sont conservées.\n' "$bin_dir"
