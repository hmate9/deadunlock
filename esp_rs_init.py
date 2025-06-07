#!/usr/bin/env python3
"""Utility to generate dynamic offsets for Rust ESP overlay."""

from __future__ import annotations

import pymem
from offset_finder import find_offsets


def main(process: str = "deadlock.exe") -> None:
    """Print the client module base address and offset mappings."""
    pm = pymem.Pymem(process)
    client_mod = pymem.process.module_from_name(pm.process_handle, "client.dll")
    client_base = client_mod.lpBaseOfDll
    offsets = find_offsets(process)
    print(f"client_base: 0x{client_base:X}")
    for key, value in offsets.items():
        print(f"{key}: 0x{value:X}")


if __name__ == "__main__":
    main()