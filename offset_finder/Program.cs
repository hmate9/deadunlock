using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
 
class Program
{
    [StructLayout(LayoutKind.Sequential)]
    public struct MODULEINFO
    {
        public IntPtr lpBaseOfDll;
        public uint SizeOfImage;
        public IntPtr EntryPoint;
    }
 
    class Signature
    {
        public string Pattern { get; }
        public uint Offset { get; }
        public uint Extra { get; }
 
        public Signature(string pattern, uint offset, uint extra)
        {
            Pattern = pattern;
            Offset = offset;
            Extra = extra;
        }
 
        public List<byte> ParsePattern()
        {
            var bytes = new List<byte>();
            var patternParts = Pattern.Split(' ');
 
            foreach (var byteStr in patternParts)
            {
                if (byteStr == "?" || byteStr == "??")
                {
                    bytes.Add(0);
                }
                else
                {
                    bytes.Add(Convert.ToByte(byteStr, 16));
                }
            }
 
            return bytes;
        }
 
        static T ReadMemory<T>(IntPtr processHandle, IntPtr address) where T : struct
        {
            var size = Marshal.SizeOf(typeof(T));
            var buffer = new byte[size];
            int bytesRead;
 
            if (ReadProcessMemory(processHandle, address, buffer, size, out bytesRead) && bytesRead == size)
            {
                GCHandle handle = GCHandle.Alloc(buffer, GCHandleType.Pinned);
                T result = (T)Marshal.PtrToStructure(handle.AddrOfPinnedObject(), typeof(T));
                handle.Free();
                return result;
            }
            throw new InvalidOperationException("Failed to read memory.");
        }
 
 
        public void Find(IEnumerable<byte> memory, IntPtr processHandle, IntPtr moduleBase)
        {
            var pattern = ParsePattern();
            var printedAddresses = new HashSet<UIntPtr>();
 
            for (int i = 0; i < memory.Count() - pattern.Count(); i++)
            {
                bool patternMatch = true;
                for (int j = 0; j < pattern.Count(); j++)
                {
                    if (pattern[j] != 0 && memory.ElementAt(i + j) != pattern[j])
                    {
                        patternMatch = false;
                        break;
                    }
                }
 
                if (patternMatch)
                {
                    var patternAddress = (UIntPtr)(moduleBase.ToInt64() + i);
                    int of = ReadMemory<int>(processHandle, (IntPtr)(patternAddress.ToUInt64() + Offset));
                    var result = patternAddress.ToUInt64() + (UInt64)of + Extra;
 
                    var resultPtr = new UIntPtr((UInt64)result - (UInt64)moduleBase.ToInt64());
 
                    // Print the address only if it's not already printed
                    if (printedAddresses.Add(resultPtr))
                    {
                        Console.WriteLine($"> 0x{resultPtr.ToUInt64():X}");
                    }
                }
            }
        }

        // Same function as above, but returns the address instead of printing it
        public ulong FindAndReturn(IEnumerable<byte> memory, IntPtr processHandle, IntPtr moduleBase)
        {
            var pattern = ParsePattern();
            var printedAddresses = new HashSet<UIntPtr>();

            for (int i = 0; i < memory.Count() - pattern.Count(); i++)
            {
                bool patternMatch = true;
                for (int j = 0; j < pattern.Count(); j++)
                {
                    if (pattern[j] != 0 && memory.ElementAt(i + j) != pattern[j])
                    {
                        patternMatch = false;
                        break;
                    }
                }

                if (patternMatch)
                {
                    var patternAddress = (UIntPtr)(moduleBase.ToInt64() + i);
                    int of = ReadMemory<int>(processHandle, (IntPtr)(patternAddress.ToUInt64() + Offset));
                    var result = patternAddress.ToUInt64() + (UInt64)of + Extra;

                    var resultPtr = new UIntPtr((UInt64)result - (UInt64)moduleBase.ToInt64());

                    // Print the address only if it's not already printed
                    if (printedAddresses.Add(resultPtr))
                    {
                        return resultPtr.ToUInt64();
                    }
                }
            }
            return 0;
        }

    }
 
    static void Main()
    {
        Console.WriteLine("By 5komar (Catrine)\n");
        Console.WriteLine("discord.gg/tcnksFMCR9\n");
 
        var localPlayerSig = new Signature("48 8B 1D ? ? ? ? 48 8B 6C 24", 3, 7);
        var viewMatrixSig = new Signature("48 8D ? ? ? ? ? 48 C1 E0 06 48 03 C1 C3", 3, 7);
        var entityListSig = new Signature("48 8B 0D ? ? ? ? C7 45 0F C8 00 00 00", 3, 7);
        var CCameraManagerSig = new Signature("48 8D 3D ? ? ? ? 8B D9", 3, 7);
        var chemas_sig = new Signature("48 89 05 ? ? ? ? 4C 8D 0D ? ? ? ? 0F B6 45 E8 4C 8D 45 E0 33 F6", 3, 7);
 
 
        string processName = "deadlock.exe";
        var processHandle = GetProcessHandle(processName);
 
        if (processHandle == IntPtr.Zero)
        {
            Console.WriteLine("Game process not found!");
            return;
        }
 
        var moduleInfo = GetModuleInfo(processHandle, "client.dll");
        var moduleInfo2 = GetModuleInfo(processHandle, "schemasystem.dll");
        if (moduleInfo.lpBaseOfDll == IntPtr.Zero)
        {
            Console.WriteLine("client.dll not found!");
            return;
        }
        if (moduleInfo2.lpBaseOfDll == IntPtr.Zero)
        {
            Console.WriteLine("schemasystem.dll not found!");
            return;
        }
 
        var memory = ReadMemoryBytes(processHandle, moduleInfo.lpBaseOfDll, (int)moduleInfo.SizeOfImage);
        var memory2 = ReadMemoryBytes(processHandle, moduleInfo2.lpBaseOfDll, (int)moduleInfo.SizeOfImage);
 
        Console.WriteLine("LocalPlayerController:");
        localPlayerSig.Find(memory, processHandle, moduleInfo.lpBaseOfDll);
        Console.WriteLine("ViewMatrix:");
        viewMatrixSig.Find(memory, processHandle, moduleInfo.lpBaseOfDll);
        Console.WriteLine("EntityList:");
        entityListSig.Find(memory, processHandle, moduleInfo.lpBaseOfDll);
        Console.WriteLine("CCameraManager:");
        CCameraManagerSig.Find(memory, processHandle, moduleInfo.lpBaseOfDll);
        Console.WriteLine("SchemaSystemInterface:");
        chemas_sig.Find(memory2, processHandle, moduleInfo2.lpBaseOfDll);

        // Now print out the results in the format:
        /*
        offsets = {
            'local_player_controller': 0x217B0F8,
            'view_matrix': 0x218CFF0,
            'entity_list': 0x1FC4480,
            'camera_manager': 0x1FE6E80,
            'schema_system_interface': 0x5E850
        }
        */
        Console.WriteLine("offsets = {");
        Console.WriteLine($"    'local_player_controller': 0x{localPlayerSig.FindAndReturn(memory, processHandle, moduleInfo.lpBaseOfDll):X},");
        Console.WriteLine($"    'view_matrix': 0x{viewMatrixSig.FindAndReturn(memory, processHandle, moduleInfo.lpBaseOfDll):X},");
        Console.WriteLine($"    'entity_list': 0x{entityListSig.FindAndReturn(memory, processHandle, moduleInfo.lpBaseOfDll):X},");
        Console.WriteLine($"    'camera_manager': 0x{CCameraManagerSig.FindAndReturn(memory, processHandle, moduleInfo.lpBaseOfDll):X},");
        Console.WriteLine($"    'schema_system_interface': 0x{chemas_sig.FindAndReturn(memory2, processHandle, moduleInfo2.lpBaseOfDll):X}");
        Console.WriteLine("}");
 
        CloseHandle(processHandle);
    }
 
    static List<byte> ReadMemoryBytes(IntPtr processHandle, IntPtr address, int size)
    {
        var buffer = new byte[size];
        ReadProcessMemory(processHandle, address, buffer, size, out _);
        return buffer.ToList();
    }
 
    static IntPtr GetProcessHandle(string processName)
    {
        processName = processName.EndsWith(".exe") ? processName.Substring(0, processName.Length - 4) : processName;
 
        var processes = Process.GetProcessesByName(processName);
        if (processes.Length > 0)
        {
            IntPtr processHandle = OpenProcess(0x0010 | 0x0400, false, processes[0].Id);
 
            if (processHandle != IntPtr.Zero)
            {
                return processHandle;
            }
            else
            {
                Console.WriteLine($"Failed to open process handle. Error code: {Marshal.GetLastWin32Error()}");
            }
        }
        else
        {
            Console.WriteLine($"No process found with name '{processName}'");
        }
 
        return IntPtr.Zero;
    }
 
    static MODULEINFO GetModuleInfo(IntPtr processHandle, string moduleName)
    {
        MODULEINFO modInfo = new MODULEINFO();
        IntPtr[] hMods = new IntPtr[1024];
        GCHandle gch = GCHandle.Alloc(hMods, GCHandleType.Pinned);
        if (EnumProcessModules(processHandle, gch.AddrOfPinnedObject(), (uint)(hMods.Length * IntPtr.Size), out uint cbNeeded))
        {
            for (int i = 0; i < (cbNeeded / IntPtr.Size); i++)
            {
                StringBuilder szModName = new StringBuilder(1024);
                if (GetModuleBaseName(processHandle, hMods[i], szModName, szModName.Capacity) > 0)
                {
                    if (moduleName == szModName.ToString())
                    {
                        GetModuleInformation(processHandle, hMods[i], out modInfo, (uint)Marshal.SizeOf(typeof(MODULEINFO)));
                        break;
                    }
                }
            }
        }
        gch.Free();
        return modInfo;
    }
 
    [DllImport("psapi.dll", SetLastError = true)]
    static extern bool EnumProcessModules(IntPtr hProcess, IntPtr lphModule, uint cb, out uint lpcbNeeded);
 
    [DllImport("psapi.dll", SetLastError = true)]
    static extern uint GetModuleBaseName(IntPtr hProcess, IntPtr hModule, StringBuilder lpBaseName, int nSize);
 
    [DllImport("psapi.dll", SetLastError = true)]
    static extern bool GetModuleInformation(IntPtr hProcess, IntPtr hModule, out MODULEINFO lpmodinfo, uint cb);
 
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool ReadProcessMemory(IntPtr hProcess, IntPtr lpBaseAddress, [Out] byte[] lpBuffer, int dwSize, out int lpNumberOfBytesRead);
 
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool ReadProcessMemory(IntPtr hProcess, IntPtr lpBaseAddress, out int lpBuffer, int dwSize, out int lpNumberOfBytesRead);
 
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr OpenProcess(int dwDesiredAccess, bool bInheritHandle, int dwProcessId);
 
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool CloseHandle(IntPtr hObject);
}