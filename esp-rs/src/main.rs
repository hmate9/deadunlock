//! Rust implementation of the Deadlock ESP overlay for high performance.

use std::{collections::HashMap, error::Error, ffi::c_void, ptr::null_mut, process::Command, thread, time::Duration, mem::{size_of, zeroed}};

use windows::core::PCWSTR;
use windows::Win32::Foundation::{HWND, LPARAM, LRESULT, WPARAM, HINSTANCE, HANDLE};
use windows::Win32::Graphics::Gdi::{BITMAPINFO, BITMAPINFOHEADER, BI_RGB, CreateCompatibleDC, CreateDIBSection, DeleteDC, DeleteObject, MoveToEx, LineTo, SelectObject, CreatePen, RGB, PS_SOLID, DIB_RGB_COLORS};
use windows::Win32::System::Diagnostics::Debug::ReadProcessMemory;
use windows::Win32::System::SystemServices::{ULW_ALPHA, AC_SRC_OVER, AC_SRC_ALPHA};
use windows::Win32::UI::WindowsAndMessaging::{CreateWindowExW, DefWindowProcW, DispatchMessageW, PeekMessageW, PostQuitMessage, RegisterClassW, TranslateMessage, UpdateLayeredWindow, WNDCLASSW, MSG, PM_REMOVE, CS_HREDRAW, CS_VREDRAW, SW_SHOW, WM_DESTROY, WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOPMOST, WS_POPUP, LWA_ALPHA, CW_USEDEFAULT, GetSystemMetrics, SM_CXSCREEN, SM_CYSCREEN};
use windows::Win32::System::Threading::{OpenProcess, PROCESS_QUERY_INFORMATION, PROCESS_VM_READ};
use windows::Win32::System::LibraryLoader::GetModuleHandleW;

const MAX_BONES: usize = 64;
const SKELETON_BASE: usize = 0x170;
const BONE_ARRAY: usize = 0x80;
const BONE_STEP: usize = 32;
const GAME_SCENE_NODE: usize = 0x330;
const INIT_SCRIPT: &str = "esp_rs_init.py";

unsafe extern "system" fn wnd_proc(hwnd: HWND, msg: u32, wparam: WPARAM, lparam: LPARAM) -> LRESULT {
    match msg {
        WM_DESTROY => {
            PostQuitMessage(0);
            LRESULT(0)
        }
        _ => DefWindowProcW(hwnd, msg, wparam, lparam),
    }
}

fn parse_offsets(output: &str) -> HashMap<String, usize> {
    let mut offsets = HashMap::new();
    for line in output.lines() {
        let parts: Vec<_> = line.split(':').map(str::trim).collect();
        if parts.len() == 2 {
            if let Some(stripped) = parts[1].strip_prefix("0x") {
                if let Ok(val) = usize::from_str_radix(stripped, 16) {
                    offsets.insert(parts[0].to_string(), val);
                }
            }
        }
    }
    offsets
}

fn world_to_screen(view: &[f32; 16], pos: (f32, f32, f32), width: i32, height: i32) -> Option<(i32, i32)> {
    let x = pos.0 * view[0] + pos.1 * view[4] + pos.2 * view[8] + view[12];
    let y = pos.0 * view[1] + pos.1 * view[5] + pos.2 * view[9] + view[13];
    let w = pos.0 * view[3] + pos.1 * view[7] + pos.2 * view[11] + view[15];
    if w < 0.1 { return None; }
    let ndc_x = x / w;
    let ndc_y = y / w;
    let sx = ((ndc_x + 1.0) * width as f32 / 2.0) as i32;
    let sy = ((1.0 - ndc_y) * height as f32 / 2.0) as i32;
    Some((sx, sy))
}

fn read_memory(handle: HANDLE, address: usize, size: usize) -> Result<Vec<u8>, Box<dyn Error>> {
    let mut buffer = vec![0u8; size];
    let mut read = 0;
    unsafe { ReadProcessMemory(handle, address as *const c_void, buffer.as_mut_ptr() as *mut c_void, size, &mut read)?; }
    buffer.truncate(read);
    Ok(buffer)
}

fn read_u64(handle: HANDLE, address: usize) -> Result<u64, Box<dyn Error>> {
    let data = read_memory(handle, address, 8)?;
    if data.len() >= 8 {
        let mut arr = [0u8; 8]; arr.copy_from_slice(&data[..8]);
        Ok(u64::from_le_bytes(arr))
    } else {
        Err("Failed to read u64".into())
    }
}

fn read_f32(handle: HANDLE, address: usize) -> Result<f32, Box<dyn Error>> {
    let data = read_memory(handle, address, 4)?;
    if data.len() >= 4 {
        let mut arr = [0u8; 4]; arr.copy_from_slice(&data[..4]);
        Ok(f32::from_le_bytes(arr))
    } else {
        Err("Failed to read f32".into())
    }
}

fn main() -> Result<(), Box<dyn Error>> {
    let output = Command::new("python").arg(INIT_SCRIPT).output()?.stdout;
    let text = String::from_utf8_lossy(&output);
    let offsets = parse_offsets(&text);
    let client_base = *offsets.get("client_base").ok_or("client_base not found")?;
    let view_matrix_offset = *offsets.get("view_matrix").ok_or("view_matrix not found")?;
    let entity_list_offset = *offsets.get("entity_list").ok_or("entity_list not found")?;
    let local_ctrl_offset = *offsets.get("local_player_controller").ok_or("local_player_controller not found")?;

    let pid_output = Command::new("powershell").arg("-Command").arg("(Get-Process -Name deadlock -ErrorAction Stop).Id").output()?.stdout;
    let pid = String::from_utf8_lossy(&pid_output).trim().parse::<u32>()?;
    let handle = unsafe { OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, false, pid).ok().ok_or("Failed to open process")? };

    let screen_width = unsafe { GetSystemMetrics(SM_CXSCREEN) };
    let screen_height = unsafe { GetSystemMetrics(SM_CYSCREEN) };
    let hinstance: HINSTANCE = unsafe { GetModuleHandleW(None)? };
    let class_name = PCWSTR::from_raw("RustESP\0".encode_utf16().collect::<Vec<_>>().as_ptr());
    let wc = WNDCLASSW { style: CS_HREDRAW | CS_VREDRAW, lpfnWndProc: Some(wnd_proc), hInstance: hinstance, lpszClassName: class_name, ..unsafe { zeroed() } };
    unsafe { RegisterClassW(&wc) };
    let hwnd = unsafe { CreateWindowExW(WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST, class_name, class_name, WS_POPUP, CW_USEDEFAULT, CW_USEDEFAULT, screen_width, screen_height, HWND(0), HWND(0), hinstance, null_mut()) };
    unsafe { ShowWindow(hwnd, SW_SHOW); windows::Win32::UI::WindowsAndMessaging::SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA) };

    let hdc = unsafe { CreateCompatibleDC(None)? };
    let mut bmi = BITMAPINFO { bmiHeader: BITMAPINFOHEADER { biSize: size_of::<BITMAPINFOHEADER>() as u32, biWidth: screen_width, biHeight: -screen_height, biPlanes: 1, biBitCount: 32, biCompression: BI_RGB, ..Default::default() }, ..Default::default() };
    let mut pixels = null_mut();
    let hbmp = unsafe { CreateDIBSection(hdc, &bmi, DIB_RGB_COLORS, &mut pixels, None, 0)? };
    let _old = unsafe { SelectObject(hdc, hbmp) };

    loop {
        let mut msg: MSG = unsafe { zeroed() };
        while unsafe { PeekMessageW(&mut msg, HWND(0), 0, 0, PM_REMOVE).as_bool() } {
            if msg.message == WM_DESTROY { return Ok(()); }
            unsafe { TranslateMessage(&msg); DispatchMessageW(&msg); }
        }
        unsafe { std::slice::from_raw_parts_mut(pixels as *mut u32, (screen_width * screen_height) as usize).fill(0); }
        let vm = read_memory(handle, client_base + view_matrix_offset, 16 * 4)?;
        let mut view = [0f32; 16];
        for i in 0..16 { let mut arr = [0u8;4]; arr.copy_from_slice(&vm[i*4..i*4+4]); view[i] = f32::from_le_bytes(arr); }
        for i in 1..16u32 {
            if let Ok(node) = (|| {
                let list = read_u64(handle, client_base + entity_list_offset)?;
                let addr = list as usize + 8 * (((i & 0x7FFF) >> 9) as usize) + 0x10;
                let base = read_u64(handle, addr)?;
                let mut ctrl = read_u64(handle, base as usize + 120 * ((i & 0x1FF) as usize))?;
                if i == 0 { ctrl = read_u64(handle, client_base + local_ctrl_offset)?; }
                let ph = read_u64(handle, ctrl as usize + 0x878)?;
                let entry = read_u64(handle, list as usize + 8 * (((ph as u32 & 0x7FFF) >> 9) as usize) + 0x10)?;
                let pawn = read_u64(handle, entry as usize + 0x78 * ((ph as u32 & 0x1FF) as usize))?;
                read_u64(handle, pawn as usize + GAME_SCENE_NODE)
            })() {
                let bones_ptr = node as usize + SKELETON_BASE + BONE_ARRAY;
                if let Ok(bones_base) = read_u64(handle, bones_ptr) {
                    if let Ok(data) = read_memory(handle, bones_base as usize, MAX_BONES * BONE_STEP) {
                        for b in 0..MAX_BONES {
                            let off = b * BONE_STEP;
                            let x = f32::from_le_bytes(data[off..off+4].try_into()?);
                            let y = f32::from_le_bytes(data[off+4..off+8].try_into()?);
                            let z = f32::from_le_bytes(data[off+8..off+12].try_into()?);
                            if let Some((sx, sy)) = world_to_screen(&view, (x, y, z), screen_width, screen_height) {
                                unsafe {
                                    let pen = CreatePen(PS_SOLID, 2, RGB(255, 0, 0));
                                    let old = SelectObject(hdc, pen);
                                    MoveToEx(hdc, sx, sy, None);
                                    LineTo(hdc, sx, sy);
                                    SelectObject(hdc, old);
                                    DeleteObject(pen);
                                }
                            }
                        }
                    }
                }
            }
        }
        unsafe {
            UpdateLayeredWindow(hwnd, None, None, Some((screen_width, screen_height)), hdc, Some((0, 0)), 0, Some((AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)), ULW_ALPHA);
        }
        thread::sleep(Duration::from_millis(16));
    }
}