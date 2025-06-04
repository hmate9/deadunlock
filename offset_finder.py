"""Utility to find Deadlock memory offsets using Windows APIs."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import struct
from dataclasses import dataclass
from typing import Dict, Optional

import psutil

from signature_patterns import SIGNATURES as SIGNATURE_PATTERNS

# Define Windows API constants
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

class MODULEINFO(ctypes.Structure):
    _fields_ = [
        ('lpBaseOfDll', wintypes.LPVOID),
        ('SizeOfImage', wintypes.DWORD),
        ('EntryPoint', wintypes.LPVOID),
    ]


def check_zero(result, func, arguments):
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    return result

# Define argtypes and restypes
psapi.EnumProcessModules.restype = wintypes.BOOL
psapi.EnumProcessModules.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
psapi.EnumProcessModules.errcheck = check_zero

psapi.GetModuleBaseNameW.restype = wintypes.DWORD
psapi.GetModuleBaseNameW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
psapi.GetModuleBaseNameW.errcheck = check_zero

psapi.GetModuleInformation.restype = wintypes.BOOL
psapi.GetModuleInformation.argtypes = [wintypes.HANDLE, wintypes.HMODULE, ctypes.POINTER(MODULEINFO), wintypes.DWORD]
psapi.GetModuleInformation.errcheck = check_zero

kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]

kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


@dataclass
class Signature:
    """Byte pattern used to locate an address in memory."""

    pattern: str
    offset: int
    extra: int

    def _parse_pattern(self):
        """Return the pattern as a list of bytes where None denotes a wildcard."""
        tokens = self.pattern.split()
        parsed = []
        for tok in tokens:
            if tok in ("?", "??"):
                parsed.append(None)
            else:
                parsed.append(int(tok, 16))
        return parsed

    def find(self, memory: bytes, base_addr: int) -> int:
        """Return the offset relative to ``base_addr`` if pattern is found."""
        pattern = self._parse_pattern()
        pat_len = len(pattern)
        size = len(memory)
        for i in range(size - pat_len):
            match = True
            for j, byte in enumerate(pattern):
                if byte is not None and memory[i + j] != byte:
                    match = False
                    break
            if match:
                offset_bytes = memory[i + self.offset : i + self.offset + 4]
                relative = struct.unpack("<i", offset_bytes)[0]
                result = base_addr + i + relative + self.extra
                return result - base_addr
        return 0


def get_process_handle(process_name: str) -> Optional[wintypes.HANDLE]:
    """Return a handle to ``process_name`` or ``None`` if it is not running."""
    name = process_name[:-4] if process_name.lower().endswith(".exe") else process_name
    for proc in psutil.process_iter(["pid", "name"]):
        if proc.info["name"].lower() in {name.lower(), process_name.lower()}:
            return kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, proc.pid)
    return None


def get_module_info(handle: wintypes.HANDLE, module_name: str) -> Optional[MODULEINFO]:
    """Return information for ``module_name`` loaded in ``handle``."""
    hmods = (wintypes.HMODULE * 1024)()
    needed = wintypes.DWORD()
    psapi.EnumProcessModules(handle, hmods, ctypes.sizeof(hmods), ctypes.byref(needed))
    count = needed.value // ctypes.sizeof(wintypes.HMODULE)
    for i in range(count):
        mod = hmods[i]
        name_buf = ctypes.create_unicode_buffer(1024)
        try:
            psapi.GetModuleBaseNameW(handle, mod, name_buf, len(name_buf))
        except WindowsError:
            continue
        if name_buf.value.lower() == module_name.lower():
            info = MODULEINFO()
            psapi.GetModuleInformation(handle, mod, ctypes.byref(info), ctypes.sizeof(info))
            return info
    return None


def read_process_memory(handle: wintypes.HANDLE, address: int, size: int) -> bytes:
    """Read ``size`` bytes from ``address`` in ``handle``."""
    buffer = (ctypes.c_char * size)()
    bytes_read = ctypes.c_size_t()
    if not kernel32.ReadProcessMemory(handle, ctypes.c_void_p(address), buffer, size, ctypes.byref(bytes_read)):
        raise ctypes.WinError(ctypes.get_last_error())
    return bytes(buffer[: bytes_read.value])


def find_offsets(process_name: str) -> Dict[str, int]:
    """Scan ``process_name`` for known signatures and return their offsets."""
    sigs = {
        name: Signature(pattern, offset, extra)
        for name, (pattern, offset, extra) in SIGNATURE_PATTERNS.items()
    }

    handle = get_process_handle(process_name)
    if not handle:
        raise RuntimeError('Game process not found')

    client = get_module_info(handle, 'client.dll')
    schemas = get_module_info(handle, 'schemasystem.dll')

    if not client or not schemas:
        kernel32.CloseHandle(handle)
        raise RuntimeError('Required modules not found')

    client_mem = read_process_memory(handle, client.lpBaseOfDll, client.SizeOfImage)
    schema_mem = read_process_memory(handle, schemas.lpBaseOfDll, schemas.SizeOfImage)

    offsets = {
        "local_player_controller": sigs["local_player_controller"].find(client_mem, client.lpBaseOfDll),
        "view_matrix": sigs["view_matrix"].find(client_mem, client.lpBaseOfDll),
        "entity_list": sigs["entity_list"].find(client_mem, client.lpBaseOfDll),
        "camera_manager": sigs["camera_manager"].find(client_mem, client.lpBaseOfDll),
        "schema_system_interface": sigs["schema_system_interface"].find(schema_mem, schemas.lpBaseOfDll),
    }

    kernel32.CloseHandle(handle)
    return offsets


def main(process_name: str = "deadlock.exe") -> None:
    """Entry point printing offsets for ``process_name``."""
    offs = find_offsets(process_name)
    print("offsets = {")
    for key, value in offs.items():
        print(f"    '{key}': 0x{value:X},")
    print("}")


if __name__ == "__main__":
    main()
