# DeadUnlock

Aimbot and ESP for Valve's Deadlock game.

## Note

This repository is provided for educational and research purposes only. Use it at your own risk.

## About

This project started as a personal learning exercise to better understand game
hacking techniques and memory manipulation. In the process we were surprised at
how limited Valve's anti-cheat measures are, given that this code continually
reads from and writes directly into the game's memory. The entire codebase is
written in Python for maximum readability while still offering surprisingly
solid performance.

## Disclaimer

The authors and contributors of this project do not endorse or encourage cheating or bypassing game security mechanisms. Any use of the code in this repository that violates the terms of service of games, software, or platforms is the sole responsibility of the user.

You are fully responsible for any consequences, including account bans or other penalties, that may result from the use of this code.

## Offset Signatures

The offset finder relies on *signatures*—unique byte patterns in the game's modules—to locate
important memory addresses such as the entity list or camera manager. These patterns are
defined in [`signature_patterns.py`](signature_patterns.py) and consumed by
`offset_finder.py` when scanning the running process.

If Valve updates Deadlock and the underlying code changes, these patterns may no longer match.
Outdated signatures will result in missing or incorrect offsets, causing other tools in this
repository to malfunction. When that happens, the signatures need to be updated by scanning the
new game binaries for the correct patterns.

## Running the Tools

### Installation

The project requires Python 3.10+ on Windows. Install the dependencies with:

```bash
pip install -r requirements.txt
```

### Aimbot

Launch Deadlock first and then start the aimbot with:

```bash
python -m deadlock.aimbot
```

The script connects to the game's process and continually adjusts your camera
towards enemy targets. When run normally it prints only setup information.
Pass ``--debug`` to enable verbose logging about target changes and aimbot
state:

```bash
python -m deadlock.aimbot --debug
```

### ESP Overlay

To render a simple ESP overlay showing player skeletons, run:

```bash
python -m deadlock.esp
```

This spawns a transparent Pygame window that follows the game and updates in
real time.
