# ⬡ Exegol-launch

> **Graphical Application Launcher** — Discover applications, find tools and launch them from a single window. Designed to run inside [Exegol](https://github.com/ThePorgs/Exegol).

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)
![Platform](https://img.shields.io/badge/Platform-Linux-informational?style=flat-square&logo=linux)
![GUI](https://img.shields.io/badge/GUI-Tkinter-green?style=flat-square)

---

## In a nutshell

Exegol-launch is a GUI tool that lets you:

- **Discover applications** installed inside an Exegol container
- **Search tools** by name, category or description
- Keep frequently used applications in **persistent favorites**
- **Launch applications in one click** while keeping the terminal available
- Add **custom commands** through a simple JSON configuration
- Read **per-application logs** when a tool fails to start

Applications run inside the container and inherit the graphical environment of the terminal. With host display sharing already configured, their windows appear on the host desktop.

**No third-party Python dependencies** — Python stdlib + Tkinter only.

---

## Table of contents

- [Installation](#installation)
- [Launch](#launch)
- [Uninstall](#uninstall)
- [Interface](#interface)
  - [Search bar](#search-bar)
  - [Applications list](#applications-list)
  - [Controls](#controls)
- [Application discovery](#application-discovery)
- [Configuration format](#configuration-format)
- [Exegol integration](#exegol-integration)
  - [Auto-install in all future containers](#auto-install-in-all-future-containers)
  - [Custom resources directory](#custom-resources-directory)
  - [Graphical session](#graphical-session)
- [Updates](#updates)
- [Troubleshooting](#troubleshooting)
- [Requirements](#requirements)
- [Contributing](#contributing)

---

## Installation

### One-liner

Run **inside an existing Exegol container, as root**:

```bash
curl -fsSL https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/main/install.sh | bash
```

To install automatically in future containers, use the **host-side** command under [Exegol integration](#exegol-integration).

### Manual

Run inside the container:

```bash
git clone https://github.com/Gvte-Kali/Exegol-launch.git
cd Exegol-launch
bash install.sh
```

The installer uses local sources when available, prefers system Python with Tkinter support and installs missing Python/Tkinter packages through apt when running as root.

| Installation mode | Application directory | Command |
|---|---|---|
| Root | `/opt/exegol-launch` | `/usr/local/bin/launch` |
| Non-root | `~/.local/share/exegol-launch`¹ | `~/.local/bin/launch` |

¹ Uses `$XDG_DATA_HOME/exegol-launch` when configured. Non-root installation requires Python 3.10+ and Tkinter to be present already. Add `~/.local/bin` to `PATH` if necessary.

No pip or virtual environment is required by the installer. Package installation with `pip install .` in a virtual environment is also supported.

Scripts can be downloaded and reviewed before execution.

---

## Launch

```bash
launch
```

Exegol-launch starts detached from the shell — **the terminal prompt returns immediately**. Closing the launcher leaves its applications running.

| Command | Description |
|---|---|
| `launch` | Open the graphical launcher |
| `launch --foreground` | Run the launcher in the foreground for diagnostics |
| `launch --list` | List detected applications without opening a window |
| `launch --version` | Display the installed version |

Applications remain dependent on the container and display server. Stopping either can stop the applications.

---

## Uninstall

Inside the container, remove the managed `launch` wrapper and its application directory using the paths listed under [Installation](#installation).

To disable automatic installation in future containers, remove the block between `# BEGIN Exegol-launch` and `# END Exegol-launch` in the host's `my-resources/setup/load_user_setup.sh`.

Unused `.exegol-launch.*` payload directories under `my-resources/setup/` can then be removed once no hook references them. Keep any backups that are still needed.

Python/Tkinter dependencies, custom commands and favorites are left untouched.

---

## Interface

The window contains a search bar, an applications list and controls for favorites, configuration and launching.

### Search bar

Search matches application names, categories and descriptions. Results update as text is entered.

| Shortcut | Action |
|---|---|
| `Ctrl+F` | Focus the search field |
| `Enter` | Launch the selected application |
| Double-click | Launch the selected application |
| `Escape` | Close the launcher |

### Applications list

| Column | Description |
|---|---|
| `★` | Favorite status |
| Application | Application name |
| Catégorie | Category from the desktop entry or custom configuration |
| Mode | GUI application or terminal command |

Categories are displayed as labels; a separate category selector is not currently implemented.

### Controls

| Control | Action |
|---|---|
| `Favoris uniquement` | Show favorite applications only |
| `Actualiser` | Reload desktop entries and custom commands |
| `★ Favori` | Toggle the selected application's favorite status |
| `Configuration` | Show the custom configuration path and format |
| `Lancer ↵` | Launch the selected application |

The status area displays application counts, warnings or the log path of the last command started. The current interface labels are in French.

---

## Application discovery

The launcher reads `.desktop` entries from the container's XDG application directories, with user entries taking precedence over system entries.

- Entries marked `Hidden` or `NoDisplay` are excluded.
- Entries whose required executable is unavailable are excluded.
- `OnlyShowIn` and `NotShowIn` restrictions are not applied to this menu.
- Burp Suite, Firefox, Wireshark, ZAP, BloodHound and Ghidra have fallback detection when their commands are available in `PATH`.

Shell aliases and functions are not executable files. Declare them explicitly in the custom configuration when needed.

---

## Configuration format

Custom applications are stored in:

```text
~/.config/exegol-launch/apps.json
```

When set, `XDG_CONFIG_HOME` replaces `~/.config`.

```json
[
  {
    "name": "Burp Suite",
    "argv": ["burpsuite"],
    "category": "Web",
    "description": "Web application testing"
  },
  {
    "name": "Working shell",
    "argv": ["bash"],
    "category": "Terminal",
    "terminal": true,
    "cwd": "/workspace"
  }
]
```

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Display name; also identifies the custom entry |
| `argv` | Yes | Non-empty list containing the executable and its arguments |
| `category` | No | Category label; defaults to `Personnel` |
| `description` | No | Additional searchable text |
| `terminal` | No | Boolean; open the command in a terminal when true |
| `cwd` | No | Working directory inside the container |

Arguments are passed directly to the process. Shell operators, `~` and `$VARIABLES` are not expanded. Use absolute paths when needed.

For a command that requires a shell, declare it explicitly, for example `["bash", "-lc", "command"]`, with the appropriate shell configuration.

See [apps.example.json](apps.example.json) for another example.

### Terminal commands

CLI tools need a terminal installed **inside the container**. A terminal command prefix can be configured with:

```bash
export EXEGOL_LAUNCH_TERMINAL='xterm -e'
```

Without this setting, the launcher searches for `x-terminal-emulator`, `xterm`, `kitty` and `alacritty`, in that order.

---

## Exegol integration

Exegol-launch runs inside the container. No launcher component needs to run on the host after installation.

### Auto-install in all future containers

Run this one-liner **on the host, as the user who runs Exegol, without sudo**:

```bash
curl -fsSL https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/main/setup-exegol.sh | bash
```

The setup script:

1. Downloads the application into `~/.exegol/my-resources/setup/`.
2. Backs up the existing `load_user_setup.sh`.
3. Adds a managed installation block after its shebang, preserving existing customizations.

Exegol runs this hook on the **first startup of each new container with my-resources enabled**. The project is installed as `/usr/local/bin/launch`.

| Location | Purpose |
|---|---|
| Host: `~/.exegol/my-resources/setup/` | Stored application sources and setup hook |
| Container: `/opt/my-resources/setup/` | Shared resources mounted by Exegol |
| Container: `/opt/exegol-launch/` | Installed application releases |
| Container: `/usr/local/bin/launch` | Launcher command |

The hook must run with root privileges. Application sources are already shared, so no GitHub download is needed during container setup. Installing missing Python/Tkinter packages through apt still requires network access.

Existing containers are not modified. A failed launcher installation prints a warning without interrupting the remaining hook customizations.

Re-running registration replaces only the managed block and prepares a new source payload. Previous payloads and backups are retained. Updates are not automatic.

See Exegol's [official setup hook template](https://github.com/ThePorgs/Exegol-images/blob/main/sources/assets/exegol/skel/load_user_setup.sh).

### Custom resources directory

If `volumes.my_resources_path` points to a different host directory:

```bash
curl -fsSL https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/main/setup-exegol.sh | bash -s -- /path/to/my-resources
```

The script does not automatically read Exegol's configuration file. Running it with sudo may select root's resources instead of the intended user's directory.

### Graphical session

The launcher inherits `DISPLAY`, `XAUTHORITY`, `WAYLAND_DISPLAY` and the rest of the terminal environment. It does not configure display sharing or change display permissions.

Tkinter on Linux generally needs an accessible X11 display, including through XWayland on a Wayland desktop. No specific desktop environment is required.

If an application already opens on the host desktop when started from the container terminal, launch Exegol-launch from that same terminal environment. A terminal configured for the VNC display will continue to use that display.

---

## Updates

Re-run the relevant installation command:

- **Existing container:** re-run `install.sh` inside that container.
- **Future containers:** re-run `setup-exegol.sh` on the host.

The installer stages application files in a new release before activation. A download failure leaves the active release in place. Previous releases and user preferences are retained.

A command named `launch` that is not marked as managed by Exegol-launch will not be overwritten. Check its origin before removing or renaming it.

### Pin a version

For a reproducible host registration, use the same commit SHA in the script URL and `EXEGOL_LAUNCH_REF`:

```bash
REF='<commit-sha>'; curl -fsSL "https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/$REF/setup-exegol.sh" | EXEGOL_LAUNCH_REF="$REF" bash
```

The same reference mechanism is available for `install.sh`.

---

## Troubleshooting

| Symptom | What to check |
|---|---|
| `launch: command not found` | Installation path and `PATH`; whether the new-container hook ran |
| Tkinter is missing | Python 3.10+ and `python3-tk` in the container |
| Display cannot be opened | Container display sharing, `DISPLAY` and graphical authorization |
| Windows appear in VNC | The display inherited from the terminal running `launch` |
| An application exits immediately | Its application log and required runtime dependencies |
| A tool is missing from the list | Its executable, desktop entry or custom JSON configuration |
| Automatic installation did not run | Correct resources directory, enabled my-resources mount and setup logs |

Logs are written under:

```text
~/.local/state/exegol-launch/
├── launcher.log
├── favorites.json
└── <application-id>.log
```

When set, `XDG_STATE_HOME` replaces `~/.local/state`. Favorites belong to each user's state directory and are not automatically shared across containers.

Use `launch --foreground` to inspect launcher startup errors. A “command started” message confirms process creation, not that an application successfully opened a window. Log files are appended to and can be removed when the relevant applications are stopped.

---

## Requirements

- Linux container running Exegol
- Python **3.10+**
- Tkinter (`python3-tk` on Debian-based images)
- Working graphical access for the container; generally X11 or XWayland for Tkinter
- Bash and curl for the installation scripts
- Python 3 and curl on the host for automatic future-container registration
- Enabled `my-resources` mount at `/opt/my-resources` for automatic installation

Automatic dependency installation supports **apt-based Exegol images**. Other environments require dependencies to be installed manually.

---

## Contributing

Bug reports and improvements are welcome through [issues](https://github.com/Gvte-Kali/Exegol-launch/issues) and pull requests.

For bug reports, include the project version, Exegol image, Python version, display mode and relevant error messages. Remove sensitive information from logs before sharing them.

### Project structure

| File or directory | Purpose |
|---|---|
| `exegol_launch/cli.py` | CLI arguments, display checks and detached startup |
| `exegol_launch/core.py` | Application discovery, configuration and processes |
| `exegol_launch/gui.py` | Tkinter interface, search and favorites |
| `exegol_launch/__main__.py` | Entry point for `python3 -m exegol_launch` |
| `install.sh` | Container installation and updates |
| `setup-exegol.sh` | Host registration for future containers |
| `apps.example.json` | Sample application configuration |
| `tests/` | Automated development checks |
| `.github/workflows/tests.yml` | GitHub Actions checks |

### Tests

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh setup-exegol.sh
```

The `tests/` directory checks discovery, command arguments, detached processes and isolated installer behavior. It is **not installed in containers** and is not required to run the launcher.

These checks do not require a graphical server. Actual graphical integration must also be validated in an Exegol container with a working display.
