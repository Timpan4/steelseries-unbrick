# Minimal: open 12E2 MI_01 HID, WriteFile [07 2c ef], close. No polling.
import ctypes, subprocess, sys, faulthandler
faulthandler.enable()
DWORD = ctypes.c_ulong
HANDLE = ctypes.c_void_p
INVALID_HANDLE = ctypes.c_void_p(-1).value
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_RW = 3
OPEN_EXISTING = 3
CreateFileW = ctypes.windll.kernel32.CreateFileW
WriteFile = ctypes.windll.kernel32.WriteFile
CloseHandle = ctypes.windll.kernel32.CloseHandle
CreateFileW.restype = HANDLE
CreateFileW.argtypes = [ctypes.c_wchar_p, DWORD, DWORD, ctypes.c_void_p, DWORD, DWORD, HANDLE]
WriteFile.restype = ctypes.c_int
WriteFile.argtypes = [HANDLE, ctypes.c_void_p, DWORD, ctypes.POINTER(DWORD), ctypes.c_void_p]
CloseHandle.argtypes = [HANDLE]

def get_paths():
    ps = r"""
$ErrorActionPreference='SilentlyContinue'
$hidGuid = '{4D1E55B2-F16F-11CF-88CB-001111000030}'
$base = "HKLM:\SYSTEM\CurrentControlSet\Control\DeviceClasses\$hidGuid"
Get-ChildItem $base -ErrorAction SilentlyContinue | ForEach-Object {
  $raw = $_.PSChildName
  if ($raw -match 'VID_1038&PID_12E2&MI_01') {
    $path = '\\?\hid#' + ($raw -replace '^##\?#HID#', '')
    Write-Output $path
  }
}
"""
    r = subprocess.run(["powershell","-NoProfile","-Command",ps], capture_output=True, text=True, timeout=30)
    return [p.strip() for p in r.stdout.splitlines() if p.strip()]

for path in get_paths():
    h = CreateFileW(path, GENERIC_READ|GENERIC_WRITE, FILE_SHARE_RW, None, OPEN_EXISTING, 0, None)
    if h == INVALID_HANDLE or h is None:
        continue
    buf = bytearray(65)
    buf[0] = 0x07; buf[1] = 0x2c; buf[2] = 0xef
    written = DWORD(0)
    ok = WriteFile(h, bytes(buf), len(buf), ctypes.byref(written), None)
    CloseHandle(h)
    print("boot-enter WriteFile ok=%s written=%d" % (ok, written.value), flush=True)
    sys.exit(0 if ok else 1)
print("no 12E2 path opened", flush=True)
sys.exit(1)
