#!/usr/bin/env python3
"""Launcher script for the aimbot GUI that works with PyInstaller."""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the GUI
from deadlock.aimbot_gui import main

if __name__ == "__main__":
    main()
