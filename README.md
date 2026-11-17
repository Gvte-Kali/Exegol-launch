# ⬡ Exegol-launch

> **Native Application Launcher** — Open XFCE Application Finder from an Exegol terminal, return the shell prompt and launch applications on the configured display.

![Platform](https://img.shields.io/badge/Platform-Linux-informational?style=flat-square&logo=linux)
![GUI](https://img.shields.io/badge/GUI-XFCE_Application_Finder-blue?style=flat-square)
![Shell](https://img.shields.io/badge/Launcher-Bash-green?style=flat-square&logo=gnubash)

---

## In a nutshell

Exegol-launch provides a **`launch` command inside Exegol** using the existing XFCE Application Finder:

- Reuse XFCE's application discovery, search and categories.
- **Return the terminal prompt** after opening the finder.
- Inherit the display configured in the container terminal.
- Start a **separate finder process**, avoiding the existing VNC desktop's D-Bus finder service.
- Install automatically in future containers through Exegol's **my-resources** setup hook.
- Optionally create a local **Caido root-mode desktop override**.

**No custom GUI, Tkinter or third-party Python modules.** The normal launcher is a Bash wrapper. Python 3 is used for host registration and the optional Caido fix.

---

## Table of contents

- [Installation](#installation)
- [Launch](#launch)
- [Caido and Electron as root](#caido-and-electron-as-root)
- [Exegol integration](#exegol-integration)
- [Updates and migration](#updates-and-migration)
- [Troubleshooting](#troubleshooting)
- [Uninstall](#uninstall)
- [Requirements](#requirements)
- [Contributing](#contributing)

---

## Installation

### One-liner

Run **inside the Exegol container**, as root:

```bash
curl -fsSL https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/main/install.sh | bash
```

The installer reuses `xfce4-appfinder` when present. If missing, it installs that package through apt when running as root. It creates `/usr/local/bin/launch` pointing to `/opt/exegol-launch/native/launch.sh`.

Non-root installation uses `${XDG_DATA_HOME:-$HOME/.local/share}/exegol-launch` and `~/.local/bin/launch`; Application Finder must already be installed. Add `~/.local/bin` to `PATH` if needed.

### Manual

```bash
git clone https://github.com/Gvte-Kali/Exegol-launch.git
cd Exegol-launch
bash install.sh
```

The installer detects local sources. Scripts can be reviewed before execution.

---

## Launch

```bash
launch
```

The process is detached using `nohup` and `setsid`, and output goes to a log. **The terminal becomes available again.** A short startup check reports immediate failures.

| Command | Description |
|---|---|
| `launch` | Open XFCE Application Finder |
| `launch --foreground` | Keep output in the terminal for diagnostics |
| `launch --collapsed` | Open XFCE's collapsed command-entry mode |
| `launch --version` | Show the wrapper version |
| `launch --fix-caido` | Create a root-local Caido override with `--no-sandbox` |

Other arguments are passed to `xfce4-appfinder`, except wrapper-specific options. `--foreground` must appear first to enable foreground mode.

The wrapper explicitly supplies **`--disable-server`** so the finder does not reuse the existing desktop's D-Bus instance. This preserves the new process's display environment; applications can still have their own single-instance behavior.

The finder and launched applications remain inside the container. Closing the finder does not normally close launched applications; stopping the container can stop them.

---

## Caido and Electron as root

An Electron application can refuse to start with this message:

```text
Running as root without --no-sandbox is not supported.
```

Changing launchers does not solve that application's startup requirement. For the installed `caido.desktop` entry, run **inside the container as root**:

```bash
launch --fix-caido
```

This creates or updates `~/.local/share/applications/caido.desktop` (or the equivalent under `XDG_DATA_HOME`), preserving the system entry. It adds `--no-sandbox` only once to Caido's main `Exec` command. An existing user override is backed up once before modification.

**This explicitly disables Electron sandboxing for Caido.** It is not applied globally or automatically to other applications. Running the application as a non-root user with working sandbox support is an alternative.

Restart Application Finder after the change. If the installed desktop filename or executable differs from the supported Caido names, the helper stops with an explanation instead of guessing how to modify it.

To undo the change, restore the `.desktop.exegol-launch.bak` file if one exists, or remove the user override to use the system entry again.

---

## Exegol integration

### Auto-install in all future containers

Run **on the host, as the user who runs Exegol, without sudo**:

```bash
curl -fsSL https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/main/setup-exegol.sh | bash
```

Resource path selection uses this order:

1. Explicit first argument or `EXEGOL_MY_RESOURCES`.
2. `volumes.my_resources_path` in `~/.exegol/config.yml` (or `EXEGOL_CONFIG_FILE`).
3. `~/.exegol/my-resources` when no custom path is configured.

A standard generated YAML mapping is supported without PyYAML. Complex YAML requires PyYAML or an explicit resource path; ambiguous configuration fails rather than silently selecting another directory.

### Custom resources directory

```bash
curl -fsSL https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/main/setup-exegol.sh | bash -s -- /path/to/my-resources
```

The script creates missing directories, validates existing files and prints the selected resource path.

### Existing files and repeated installation

| Item | Behavior |
|---|---|
| Existing `load_user_setup.sh` | Preserved outside the managed block |
| Existing Exeflow or other custom setup | Preserved |
| Duplicate complete Exegol-launch blocks | Collapsed into one block |
| Malformed block | Registration stops without modifying the hook |
| Active sources | One `setup/exegol-launch/` directory |
| Backup | One initial `load_user_setup.sh.exegol-launch.bak` |
| Concurrent registration | Serialized using a filesystem lock |
| Incomplete download or invalid script | Existing hook and payload remain available |
| Old generated Python payload folders | Removed when identified as this project's managed legacy payloads |

Historic backups from older releases are preserved. Arbitrary similarly named user folders are not removed.

### First startup

Exegol must have **my-resources enabled and mounted at `/opt/my-resources`**. At the first startup of a new container, its hook runs:

```text
/opt/my-resources/setup/load_user_setup.sh
  → /opt/my-resources/setup/exegol-launch/install.sh
  → /usr/local/bin/launch
```

The hook runs the installer as root. Sources are already shared; installing a missing apt package still needs network access. Installation status uses Exegol's tagged output so failures are visible in the host terminal.

Exegol's overall “Successfully deployed my-resources” message is **not proof** that every user setup command succeeded. Inspect `/var/log/exegol/load_setups.log` or `.log.gz` inside the container if necessary.

Existing containers are not retroactively initialized: use the container installer for them. The setup mechanism is described in Exegol's [official hook template](https://github.com/ThePorgs/Exegol-images/blob/main/sources/assets/exegol/skel/load_user_setup.sh).

---

## Updates and migration

Version **0.2** replaces the project's Python/Tkinter interface with XFCE Application Finder. There is no second application menu to maintain.

- Re-run `install.sh` inside an existing container to replace the managed `launch` command.
- Re-run `setup-exegol.sh` on the host to update future-container installation.
- Unrelated commands named `launch` are not overwritten.
- Previous managed Python application releases are removed after successful migration. Python/Tkinter system packages are not uninstalled.
- Old custom JSON and favorite files are retained as user data, but are not used by Application Finder. Use desktop entries and XFCE's own settings instead.
- The previous `--list` option is not provided by this native wrapper.

For reproducible registration, use a commit SHA both in the script URL and `EXEGOL_LAUNCH_REF`:

```bash
REF='<commit-sha>'; curl -fsSL "https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/$REF/setup-exegol.sh" | EXEGOL_LAUNCH_REF="$REF" bash
```

The same mechanism is available for `install.sh`. Updates are explicit, not automatic.

---

## Troubleshooting

| Symptom | What to check |
|---|---|
| `launch: command not found` | Container installation, `PATH`, setup hook logs; use `rehash` in zsh |
| Application Finder missing | Re-run the installer or install `xfce4-appfinder` |
| No window | Use `launch --foreground`; verify the terminal's display access |
| Finder appears in VNC | Check `DISPLAY` and `WAYLAND_DISPLAY` inherited from that terminal |
| Application appears in an existing session | The application may independently reuse its own running instance |
| Caido root error | Use the explicit `launch --fix-caido` workaround or run Caido as non-root |
| Automatic installation missing | Verify the printed host resources path matches the mounted Exegol volume |
| Registration refuses a symlink or malformed hook | Review the existing hook rather than overwriting its target |

Finder logs: `${XDG_STATE_HOME:-$HOME/.local/state}/exegol-launch/appfinder.log`.

The wrapper does not invent display addresses, modify graphical permissions or configure Docker display sharing. Application Finder's interface language follows the installed XFCE translations and process locale.

---

## Uninstall

Remove the managed `/usr/local/bin/launch` symlink and `/opt/exegol-launch` inside the container, or the corresponding non-root paths.

On the host, remove the block from `# BEGIN Exegol-launch` through `# END Exegol-launch` in `my-resources/setup/load_user_setup.sh`. Then remove `setup/exegol-launch/` if it is no longer referenced. Keep any backups still needed.

An optional Caido override is user configuration and must be removed or restored separately. XFCE packages are not uninstalled automatically.

---

## Requirements

- Exegol container with graphical access to its intended display
- Bash, `xfce4-appfinder`, `nohup`, `setsid`, `flock` and standard Linux utilities
- curl for remote container installation
- Python 3 on the host for registration, and in the container only for the optional Caido helper
- Writable resources directory and my-resources enabled for future-container integration

Automatic package installation supports apt-based containers. Other environments require Application Finder and system utilities to be installed manually.

---

## Contributing

Issues and pull requests are welcome. Include the Exegol image, installed version, display configuration and useful error output when reporting bugs. Remove sensitive data before sharing logs.

| File | Purpose |
|---|---|
| `launch.sh` | Detached native finder wrapper |
| `install.sh` | Container installation and migration |
| `setup-exegol.sh` | Host resource detection and idempotent registration |
| `fix-caido.py` | Optional local Caido desktop override |
| `tests/test_native.py` | Isolated regression tests |

```bash
python3 -m unittest discover -s tests -v
bash -n launch.sh install.sh setup-exegol.sh
```

Tests use a stand-in finder to verify arguments and inherited display, plus real filesystem registration and installer operations. They do not replace testing with an actual Exegol graphical session.
