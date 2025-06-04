import ctypes
from ctypes import wintypes
import struct
import psutil

# Define Windows API constants
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)

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


class Signature:
    def __init__(self, pattern: str, offset: int, extra: int) -> None:
        self.pattern = pattern
        self.offset = offset
        self.extra = extra

    def _parse_pattern(self):
        tokens = self.pattern.split()
        parsed = []
        for tok in tokens:
            if tok in ('?', '??'):
                parsed.append(None)
            else:
                parsed.append(int(tok, 16))
        return parsed

    def find(self, memory: bytes, base_addr: int) -> int:
        pattern = self._parse_pattern()
        pat_len = len(pattern)
        size = len(memory)
        for i in range(size - pat_len):
            match = True
            for j, b in enumerate(pattern):
                if b is not None and memory[i + j] != b:
                    match = False
                    break
            if match:
                offset_bytes = memory[i + self.offset: i + self.offset + 4]
                relative = struct.unpack('<i', offset_bytes)[0]
                result = base_addr + i + relative + self.extra
                return result - base_addr
        return 0


def get_process_handle(process_name: str):
    name = process_name[:-4] if process_name.lower().endswith('.exe') else process_name
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'].lower() == name.lower() or proc.info['name'].lower() == process_name.lower():
            return kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, proc.pid)
    return None


def get_module_info(handle, module_name: str) -> MODULEINFO:
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


def read_process_memory(handle, address: int, size: int) -> bytes:
    buffer = (ctypes.c_char * size)()
    bytes_read = ctypes.c_size_t()
    if not kernel32.ReadProcessMemory(handle, ctypes.c_void_p(address), buffer, size, ctypes.byref(bytes_read)):
        raise ctypes.WinError(ctypes.get_last_error())
    return bytes(buffer[:bytes_read.value])


def find_offsets(process_name: str):
    sigs = {
        'local_player_controller': Signature('48 8B 1D ? ? ? ? 48 8B 6C 24', 3, 7),
        'view_matrix': Signature('48 8D ? ? ? ? ? 48 C1 E0 06 48 03 C1 C3', 3, 7),
        'entity_list': Signature('48 8B 0D ? ? ? ? C7 45 0F C8 00 00 00', 3, 7),
        'camera_manager': Signature('48 8D 3D ? ? ? ? 8B D9', 3, 7),
        'schema_system_interface': Signature('48 89 05 ? ? ? ? 4C 8D 0D ? ? ? ? 0F B6 45 E8 4C 8D 45 E0 33 F6', 3, 7),
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
        'local_player_controller': sigs['local_player_controller'].find(client_mem, client.lpBaseOfDll),
        'view_matrix': sigs['view_matrix'].find(client_mem, client.lpBaseOfDll),
        'entity_list': sigs['entity_list'].find(client_mem, client.lpBaseOfDll),
        'camera_manager': sigs['camera_manager'].find(client_mem, client.lpBaseOfDll),
        'schema_system_interface': sigs['schema_system_interface'].find(schema_mem, schemas.lpBaseOfDll),
    }

    kernel32.CloseHandle(handle)
    return offsets


if __name__ == '__main__':
    offs = find_offsets('deadlock.exe')
    print('offsets = {')
    for key, value in offs.items():
        print(f"    '{key}': 0x{value:X},")
    print('}')
