# DeadUnlock

<p align="center">
  <img src="img/deadunlock_icon.png" alt="Project icon" width="128">
</p>

Aimbot and ESP for Valve's Deadlock game.

<p align="center">
  <img src="img/output.gif" alt="Demo of DeadUnlock in action" width="600">
</p>

This is an **external hack**, meaning the scripts run in a separate
process and manipulate the game's memory from the outside rather than
injecting code into the executable. It uses standard Windows APIs to
read and write memory, keeping the hack isolated from the game
process.

## Downloads 

Builds are automatically generated on every push and published under the
[releases](https://github.com/hmate9/deadunlock/releases). Grab the latest
`deadunlock.exe` from the
[latest release](https://github.com/hmate9/deadunlock/releases/latest).

## About

This project started as a personal learning exercise to better understand game
hacking techniques and memory manipulation. In the process we were surprised at
how limited Valve's anti-cheat measures are, given that this code continually
reads from and writes directly into the game's memory. The entire codebase is
written in Python for maximum readability while still offering surprisingly
solid performance.

## Note

This repository is provided for educational and research purposes only. Use it at your own risk.

## Disclaimer

The authors and contributors of this project do not endorse or encourage cheating or bypassing game security mechanisms. Any use of the code in this repository that violates the terms of service of games, software, or platforms is the sole responsibility of the user.

You are fully responsible for any consequences, including account bans or other penalties, that may result from the use of this code.

## Running the Tools

### Installation

The project requires Python 3.10+ on Windows. Install the dependencies with:

```bash
pip install -r requirements.txt
```

Both the aimbot and ESP will check for updates on startup and will
automatically run ``git pull`` if your local copy is out of date.

### Aimbot

Launch Deadlock first and then start the aimbot with:

```bash
python -m deadlock.aimbot
```

Pass ``--debug`` to print detailed log messages which can help when
troubleshooting:

```bash
python -m deadlock.aimbot --debug
```

The script connects to the game's process and continually adjusts your camera
towards enemy targets.

The aimbot automatically selects the closest target when you hold down the left
mouse button. If you want to shoot without the aimbot—for example at troopers,
towers or souls—hold the right mouse button instead and make sure to remap the
alternate fire key in Deadlock's settings so it doesn't conflict.

#### Headshot targeting

The aimbot can aim for either the head or center mass of targets based on the
`headshot_probability` setting (default 25%). To make targeting behavior more
consistent and human-like, the aimbot caches its headshot decision for 0.4
seconds at a time. This means that once the aimbot decides whether to aim for
the head or body, it will maintain that targeting preference for the next 0.4
seconds before making a new random decision. This prevents rapid switching
between head and body targeting that could appear unnatural.

If no enemy has been targeted for more than two seconds, the
`headshot_on_acquire` setting (enabled by default) forces headshots for the next
0.4 seconds when a new target is acquired.

#### Hero ability lock

When playing **Grey Talon** or **Yamato**, pressing **Q** (ability 1) keeps the
aimbot locked on your target for a short duration. Using **Vindicta's** **R**
(ability 4) triggers the same lock. These timeouts can be changed through
``AimbotSettings`` (`grey_talon_lock`, `yamato_lock`, and `vindicta_lock`). The
hotkeys can also be configured (`grey_talon_key`, `yamato_key`, and
`vindicta_key`) or toggled completely using the GUI.

For **Paradox**, pressing **R** automatically fires **E** after 0.05 seconds.
Both keys can be changed via ``paradox_r_key`` and ``paradox_e_key`` and the
shortcut can be disabled with ``paradox_shortcut_enabled``.

A small Tkinter GUI is available as well:

```bash
python -m deadlock.aimbot_gui
```

It lets you tweak the aimbot settings, enable or disable the hero ability
locks and change the keys used to trigger them.

### ESP Overlay

To render a simple ESP overlay showing player skeletons, run:

```bash
python -m deadlock.esp
```

To get verbose output while the overlay runs, add ``--debug``:

```bash
python -m deadlock.esp --debug
```

This spawns a transparent Pygame window that follows the game and updates in
real time.

The overlay is also handy for discovering bone indexes for each hero. When
Valve updates a character model, running it lets you read the new bone numbers
and update the head and body mappings stored in
[`deadlock/heroes.py`](deadlock/heroes.py).

## Offset Signatures

The offset finder relies on *signatures*—unique byte patterns in the game's modules—to locate
important memory addresses such as the entity list or camera manager. These patterns are
defined in [`signature_patterns.py`](signature_patterns.py) and consumed by
`offset_finder.py` when scanning the running process.

All offsets derived from these patterns are stored in
[`deadlock/mem_offsets.py`](deadlock/mem_offsets.py).  This module is imported
throughout the project to avoid sprinkling magic numbers across the codebase.

If Valve updates Deadlock and the underlying code changes, these patterns may no longer match.
Outdated signatures will result in missing or incorrect offsets, causing other tools in this
repository to malfunction. When that happens, the signatures need to be updated by scanning the
new game binaries for the correct patterns.

## Building a standalone executable

You can package the GUI into a single Windows executable using
[PyInstaller](https://pyinstaller.org/). Install it first:

```bash
pip install pyinstaller
```

Then create the executable with:

```bash
pyinstaller deadunlock.spec
```

The resulting `.exe` will be placed in the `dist` folder and can be run on
machines without Python installed.

## Contributing

Contributions are very welcome. If you have ideas or fixes, fork the repository, create a feature branch and open a pull request against `main`.
Run the following to make sure all Python files compile before submitting:

```bash
python -m py_compile $(git ls-files '*.py')
```

### Project structure

- The repository is organised as follows:

- `deadlock/` – Python package with the main functionality:
  - `__init__.py` – exposes the public API and lazily loads optional modules.
  - `aimbot.py` – implements the aimbot logic and input handling.
  - `aimbot_gui.py` – Tkinter interface for configuring and running the aimbot.
  - `esp.py` – pygame overlay drawing simple player skeletons.
  - `gui_utils.py` – helper functions used by the GUI.
  - `heroes.py` – hero enumeration and bone lookups.
  - `helpers.py` – vector math and coordinate conversion utilities.
  - `memory.py` – wrapper over ``pymem`` for reading game memory.
  - `mem_offsets.py` – central location for hardcoded memory offsets.
  - `update_checker.py` – utilities for checking GitHub for new releases.
- `launcher.py` – entry point used when bundling the GUI with PyInstaller.
- `offset_finder.py` – scans the game to find updated memory offsets.
  - `signature_patterns.py` – byte patterns consumed by the offset finder.
  - `deadunlock.spec` – PyInstaller configuration for building an executable.
- `version.txt` – text file storing the current version string.
- `img/` – images used in the README and GUI icons.

