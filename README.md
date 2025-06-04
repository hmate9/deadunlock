# DeadUnlock

Aimbot and ESP for Valve's Deadlock game.

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

#### Hero ability lock

When playing **Grey Talon** or **Yamato**, pressing **Q** (ability 1) keeps the
aimbot locked on your target for a short duration. Using **Vindicta's** **R**
(ability 4) triggers the same lock. These timeouts can be changed through
``AimbotSettings`` (`grey_talon_lock`, `yamato_lock`, and `vindicta_lock`). The
hotkeys can also be configured (`grey_talon_key`, `yamato_key`, and
`vindicta_key`) or toggled completely using the GUI.

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
pyinstaller --onefile deadlock/aimbot_gui.py
```

The resulting `.exe` will be placed in the `dist` folder and can be run on
machines without Python installed.
