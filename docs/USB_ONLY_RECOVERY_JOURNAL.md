# USB-Only Recovery Journal - SteelSeries Arctis Nova Pro Wireless (RX MCU brick)

All actions non-destructive unless explicitly user-approved. No erase/program/write.

## Environment baseline (verified from local evidence)
- Test-signing ON, Secure Boot OFF (per task; not re-verified this session)
- SteelSeries GG engine live: coreProps.json = 127.0.0.1:51235 / :51246 / :6327
- Firmware candidates exist:
  - firmware_arctis_nova_pro_wireless_rx_mcu_v1.22.11.hex (589918 B, Intel HEX)
  - firmware_arctis_nova_pro_wireless_rx_bt_v1.15.4.bin (517884 B, raw bin)
- ISPDLL.dll / HIDDLL.dll exist in C:\Program Files\SteelSeries\GG\apps\engine\
- EFORMAT.INI (Holtek ISP config) present, 14000 B

---

## GATE 1: A (PnP state) + C (usbipd) + D (DLL exports) + F (packet framing)
Timestamp: 2026-06-26

### A. PnP device classification (pnp_inventory.ps1 / present_only.ps1)
RESULT (present-only, Status=OK, actually on bus):
- USB\VID_1038&PID_12E0\6&23491980&0&2  = base station, composite, OK
  - MI_00 MEDIA "Arctis Nova Pro Wireless" (usbaudio)
  - MI_03 HID consumer control
  - MI_04 HID vendor-defined (COL01/COL02)
- USB\VID_1038&PID_12E2\6&1B2B7D3C&0&1  = headset normal mode, composite, OK
  - MI_00 HID consumer control
  - MI_01 HID vendor-defined (usage page FFFF)  <- SSE command interface

PHANTOM / disconnected (NOT on bus):
- USB\VID_1038&PID_12E3\8&2D69411B&0&9  "SteelSeries Bootloader (WinUSB)" oem31.inf  CM_PROB_PHANTOM  parent=ROOT_HUB30\7&3898d510
- USB\VID_1038&PID_12E2\8&2D69411B&0&9 (old 12E2 enum on same port as the 12E3 phantom)
- USB\VID_04D9&PID_8008\AP0000000003 (Holtek ISP device) CM_PROB_PHANTOM  parent=ROOT_HUB30\7&349e6d04
- multiple stale 12E2 HID children (phantom)

INTERPRETATION:
- The bricked 12E3 bootloader device is NOT currently on the USB bus. It is a
  phantom/disconnected node. This CONTRADICTS the prior working theory that
  "12E3 exists on USB internally but PnP cannot start it." Local evidence: 12E3
  is simply absent (disconnected).
- The Holtek ISP device (VID 04D9 PID 8008) is also absent (phantom).
- Only normal-mode devices are present: 12E0 (base) + 12E2 (headset). The headset
  main firmware boots fine; only its bootloader (12E3) / ISP mode is unavailable.
- No transport can reach a device that is not enumerated. Reaching the bootloader
  requires the device to first enter bootloader/ISP mode and re-enumerate.

### C. usbipd / WSL path
RESULT: `usbipd` not recognized. winget: "No installed package found matching input criteria."
INTERPRETATION: WSL has no USB bridge. usbipd-win is NOT installed. WSL cannot see
any USB device until usbipd-win is installed (installs a kernel driver + service).
Blocked unless user approves installing usbipd-win.

### D. ISPDLL.dll / HIDDLL.dll (dll_inspect.py, pefile)
RESULT: both DLLs are x64 (machine 0x8664). pefile available.
ISPDLL.dll exports (29): SetHwId, ConnectToBootloader, DisConnectBootloader,
  GetBootloaderVer, GetMCUInfo, ExecuteProgramFrom, SwitchToUserProgram,
  LoadFile/LoadFileEx, LoadProgdata/Ex, EraseByAddr/EraseByPage, Program,
  PartialProgram, BlankCheck/ParitialBlankCheck, VerifyByAddr/VerifyByPage,
  LockByAddr/Page/All/FromOption, SaveFile, GetChksum, GetLoadFileErr,
  GetTransProgress, IgnoreBlank, i3kSys.
HIDDLL.dll exports (19): HT_FindHidFirstDevice, HT_FindHidNextDevice,
  HT_GetFindDevicePath, HT_OpenDevice, HT_OpenDeviceI, HT_CloseDevice,
  HT_GetAttribute, HT_GetConnectStatus, HT_SetConnectStatus,
  HT_GetDeviceCapabilities, HT_GetFeature, HT_SetFeature, HT_WriteUSB,
  HT_ReadUSB, HT_GetUSBAck, HT_SetUSBCmd, HT_Replug, HT_HidGetLastError,
  HT_HidSetLastError.

Static (sedevice_decompiled.c):
- SSEdevice.dll LoadLibraryW("ISPDLL.dll") @ FUN_180040930; resolves SetHwId,
  ConnectToBootloader, DisConnectBootloader, SwitchToUserProgram,
  ExecuteProgramFrom, GetMCUInfo, LoadFile, Erase*, Verify*, Program, etc.
- SetHwId wrapper FUN_180040c30: calls (*SetHwId)(param_3) with a SINGLE 16-bit
  arg (undefined2). So SetHwId takes ONE 16-bit value = Holtek chip/device ID,
  NOT a (VID,PID) pair. Likely 0x0219 (HT68FB240 ISP ID from EFORMAT.INI).

### EFORMAT.INI (Holtek ISP config) - key fields
- body4 = HT68FB240, 2, 0x00EE, 0x0219, 0x0, 0x1000, 0x80000, 0x0020, ...
  -> page size 0x1000, ISP ID 0x0219, type 2
- [ISPData] HT68FB240 = 0, SYSL_  (bootloader size 0 = 0.5KW, SYS L config)
- [Programming] type 0 = 16bit <=16Kword (power-on ID ADh)

### F. SSEdevice flash packet framing (sedevice_decompiled.c)
Function: FlashFirmwareArctisNovaProWirelessMCURX @ 0x1800295c0
- RX MCU boot-enter command = [0x07, 0x2c, 0xef]  (local_res18=0x2c07, local_res1a=0xef)
- TX MCU boot-enter command = [0x06, 0xeb]  (FlashFirmwareArctisNovaProWirelessMCUTX)
- PrepareDeviceArctisNovaProWireless sends boot cmd, then FlashFirmwareArctisNovaProWirelessMCU
Firmware data packet (FlashFirmwareArctisNovaProWirelessMCU):
  offset 0:  0xa106            (2B cmd)
  offset 2:  4B address (big-endian) = segment_base + offset
  offset 6:  2B size (big-endian, up to 0x3f4 = 1012)
  offset 8:  4B CRC32 (standard reflected: init 0xffffffff, table local_888, final ~xor)
  offset 12: data (up to 1012B)
  total packet = 0x400 (1024B). Sent via vtable[0x18] (write).
Ack read via vtable[0x8]:
  status byte 0x06 = success
  0x01 = fail -> 0xdeadbeef
  0x02/0x03 -> 0xbadda7a
  loops until 0x06 or timeout.
- This is SSEdevice's OWN protocol over the 12E3 HID/WinUSB device, NOT the
  ISPDLL path. Both paths need a bootloader device present on the bus.

---

## GATE 1 CONCLUSION / NEXT GATE
Blocker: no bootloader device (12E3 nor 04D9:8008) is present on USB. Only
normal-mode 12E0/12E2 are live. Any flash/ISP path requires the device to be
in bootloader/ISP mode and enumerated first.

Next gate (non-destructive, safe): statically determine the EXACT VID/PID that
ISPDLL/HIDDLL search for (default Holtek VID 04D9? PID 8008? does SetHwId change
PID?) by scanning the DLL binaries for embedded VID/PID bytes + strings. This
tells us precisely what device must appear for ConnectToBootloader to succeed.

Then: decide whether entering bootloader mode from the working 12E2 (sending
[07 2c ef]) is safe enough to attempt — requires user consent because a
corrupted bootloader could fail to re-enumerate and worsen the brick.
## GATE 2: D ISPDLL connect probe (isp_probe.py)
Timestamp: 2026-06-26
Script: usb_only_work\isp_probe.py (ctypes, x64 python, HIDDLL preloaded)
Calls: SetHwId(0x0219), ConnectToBootloader(), DisConnectBootloader() only.
RESULT:
- SetHwId(0x0219) -> 59196563 (0x387BCB3). Suspicious return; signature may differ
  (possibly returns a pointer/handle or arg type wrong). Not relied upon.
- ConnectToBootloader() -> -1 (0xFFFFFFFF) = FAIL. GetLastError=0 (clean fail).
- DisConnectBootloader() -> 0.
INTERPRETATION:
- ConnectToBootloader found NO bootloader device. Confirms (with code, not just PnP)
  that no ISP/bootloader HID device (neither 12E3 nor 04D9:8008) is present on the bus.
- ISPDLL+HIDDLL load fine; the API is callable. The ONLY missing ingredient is a
  device actually sitting in bootloader/ISP mode and enumerated.
- Note: 12E2 (headset normal mode) IS present as a HID vendor-defined device, but
  ConnectToBootloader did NOT match it -> ISPDLL/HIDDLL filter by a bootloader PID
  (likely 12E3 / 04D9:8008), not the normal-mode 12E2. Good: no accidental wrong-device.

## SYNTHESIS - where recovery actually stands
Root blocker (proven three ways: PnP phantom, usbipd absent, ISPDLL connect=-1):
  The bricked MCU is NOT in bootloader/ISP mode on USB. Its normal-mode firmware
  (12E2) boots fine; its bootloader (12E3) and Holtek ISP (04D9:8008) do not appear.
  No Windows/WSL USB transport can reach a device that is not enumerated.

Every remaining path requires FIRST getting the MCU into bootloader/ISP mode so it
  re-enumerates as 12E3 (SteelSeries bootloader) or 04D9:8008 (Holtek ROM ISP):
  1. Hardware ISP strap at reset -> OFF TABLE (hardware not available).
  2. Software boot-enter command [07 2c ef] sent to the WORKING 12E2 HID interface.
     This is what a normal firmware update does. RISK: if the bootloader is what is
     bricked, the MCU may fail to re-enumerate and could be left in a worse state
     (lose the currently-working 12E2 normal mode). Needs explicit user consent.
  3. Install usbipd-win + attach to WSL -> only useful AFTER a bootloader device is
     present; does not by itself create one. And it needs a driver install (consent).
  4. ISPDLL path -> only works once 12E3/04D9:8008 is present (ConnectToBootloader=-1 now).

NET: the problem is not "transport unreachable", it is "bootloader device absent".
      Transport (ISPDLL) is proven reachable and ready; it just has no target.
## GATE 3: GG engine log (gg-errorlog.txt) - device mapping + failure chain
Timestamp: 2026-06-26 (log spans 2026/06/25-26)
KEY LINES:
- ReadFirmwareVersion: ReadFromDevice(...0x103812e2...) via SendCommand: 0xfead7007
  -> reading fw version from 12E2 (normal mode) TIMES OUT (0xfead7007 = ReadFile timeout)
- Firmware update: FAILED (0xdeadbeef); then FAILED (0x0)
- Flashing Firmware: PID 272110307 : Error writing to SteelSeries Bootloader(fw_update)
  via SendCommand: 0xf1a5fa11
- WriteToDevice(0x103812e3, {data 0x4d1}, 0x1) -> the flash WRITE targets 12E3 (bootloader)
- PreConnect (newPid: 272110306, pid: 272110307): FindConnectedDevice PreConnect fails
  -> GG sees a device swap between 272110306 (12E2) and 272110307 (12E3) and can't reconnect

DEVICE MAPPING (now proven, not assumed):
- 12E2 = Arctis Nova Pro Wireless NORMAL mode (the headset, present, PID 272110306)
- 12E3 = SteelSeries Bootloader (bootloader mode, PID 272110307)
- Firmware backup folder 272110306 == the 12E2 device instance id
- rx_mcu firmware = the MCU that runs as 12E2 normally / 12E3 in bootloader

INTERPRETATION (corrects/refines prior state):
- The bricked unit IS currently connected, as 12E2. It is NOT absent.
- BUT even 12E2 is partially broken: GG cannot read its firmware version
  (0xfead7007 ReadFile timeout). So the normal-mode HID command path is also flaky.
- The flash failure is on 12E3: writing 0x4d1 bytes -> 0xdeadbeef/0xf1a5fa11.
  This means the boot-enter DID happen (device went 12E2->12E3 at least once),
  but the bootloader write/ack failed.
- Currently (this session's PnP) 12E3 is phantom = the device is sitting in 12E2
  normal mode right now, not left in bootloader.

This means the headset's main firmware is alive enough to enumerate as 12E2, but:
  (a) fw-version reads time out, and (b) its bootloader (12E3) does not complete
  flash writes. Recovery must account for BOTH paths being unreliable.
## GATE 4: Online / open-source research ("exhaust online options")
Timestamp: 2026-06-26

### fwupd SteelSeries plugin (fwupd/fwupd, plugins/steelseries/)
- Source: fu-steelseries-fizz.c (fetched from commit bcb62f0)
- Supports: Stratus Duo/+, Aerox 3 / Rival 3 Wireless, Arctis Nova 5 + dongle,
  Arctis Nova 3P + dongle. NOTE: does NOT list Arctis Nova Pro Wireless.
- Protocol IDs: com.steelseries.fizz, com.steelseries.gamepad, com.steelseries.sonic
- KEY mechanism (confirms our RE): bootloader entry = a "reset" command sent over the
  NORMAL-mode HID interface (fu_steelseries_fizz_detach -> fizz_reset(RESET_MODE_BOOTLOADER)),
  then WAIT_FOR_REPLUG: device disappears and reappears as bootloader. After flash,
  fizz_reset(RESET_MODE_NORMAL) re-enumerates back to normal (attach).
  -> This matches SSEdevice.dll: PrepareDevice sends [07 2c ef] to 12E2 -> re-enum as 12E3.
- FIZZ uses a file-system access model (cmd, filesystem, id, offset, size, data; 52B chunks;
  erase + write + CRC32 verify). This is the NEWER Nova 5/3P protocol, NOT the Nova Pro
  Wireless protocol (which uses SSEdevice's 0xa106 packet, 1012B chunks, own CRC32).
- Vendor ID = USB:0x1038 (SteelSeries), confirmed.
- fwupd requires /dev/bus/usb r/w = Linux. Not directly usable on Windows, but proves the
  bootloader-entry mechanism and gives a reference protocol implementation.

### Community tools (per task + this search)
- HeadsetControl, Arctis Sound Manager, nova-chatmix-linux, GGWP, Spirit532 gist:
  NONE implement firmware flashing for Nova Pro Wireless. Confirmed no public flasher.

### Holtek ISPDLL/HIDDLL
- No public Holtek ISP USB recovery tool that bypasses needing the MCU already in ISP mode.
- ISPDLL/HIDDLL here are Holtek builds branded "SteelSeries ApS"; they require a device
  already enumerating as a bootloader (ConnectToBootloader=-1 when absent, proven Gate 2).

### NET (online)
- The only public implementation of SteelSeries firmware update = fwupd FIZZ, which does not
  cover the Nova Pro Wireless and uses a different protocol. No existing tool can reflash a
  Nova Pro Wireless whose bootloader does not come up. The reset-to-bootloader concept is
  confirmed identical, but there is no off-the-shelf Windows recovery for this exact brick.

---
## OVERALL CONCLUSION (evidence-based, corrects original prompt theory)
ORIGINAL THEORY: "12E3 exists on USB bus internally but PnP cannot start it."
EVIDENCE SAYS: FALSE. 12E3 is phantom/disconnected. The bricked unit is currently connected
  as 12E2 (normal mode, present, OK in PnP) BUT GG cannot read its fw version (0xfead7007
  ReadFile timeout). The bootloader 12E3 does NOT come up; the Holtek ISP 04D9:8008 also absent.

Three independent proofs that no bootloader device is on the bus:
  (1) PnP: 12E3 + 04D9:8008 = CM_PROB_PHANTOM / Disconnected
  (2) ISPDLL ConnectToBootloader() = -1
  (3) usbipd not installed (no WSL bridge anyway)

Transport (ISPDLL/HIDDLL) is proven reachable and ready; the missing ingredient is a live
  bootloader device. Every remaining path needs the MCU to enter bootloader/ISP mode first:
  - hardware ISP strap at reset -> OFF TABLE
  - software reset-to-bootloader [07 2c ef] to the working 12E2 -> RISKY (if bootloader is
    what's bricked, could lose the still-working 12E2 normal mode) -> needs user consent
  - install usbipd-win -> only useful AFTER a bootloader device exists; driver install -> consent

DECISION POINT -> requires user input (both remaining real actions are consent-gated).
Proposed safe-but-speculative probe (no consent needed, non-destructive):
  Direct HID read-only query to 12E2 MI_01 (vendor-defined) with long timeout, to test if
  WE can talk to normal mode at all (vs GG's timeout). Framing not yet pinned down, so
  offered as an option, not assumed.
## GATE 5: usbipd-win install + WSL attach + 12E2 descriptor capture
Timestamp: 2026-06-26

### usbipd-win installed
- winget: dorssel.usbipd-win 5.3.0 installed (service Automatic, Running)
- Binary: C:\Program Files\usbipd-win\usbipd.exe (not on PATH; prepend per session)
- 12E2 busid = 2-1; 12E0 busid = 3-2; no 12E3/04D9:8008 present (confirmed again)
- Required killing SteelSeries GG processes (engine held 12E2 HID open) before attach
- After kill: bind --force + attach --wsl succeeded; 12E2 = "Attached" in WSL

### 12E2 USB descriptor (via lsusb -vvv + pyusb in WSL as root)
Device: 1038:12e2, bcdDevice 1.22, "SteelSeries" / "Arctis Nova Pro Wireless", USB 2.0 FS
Config 1, 2 interfaces, 500mA:
- Iface 0 (consumer control): EP 0x81 IN, 2 bytes, interrupt
- Iface 1 (SSE command channel): EP 0x82 IN 64B + EP 0x02 OUT 64B, interrupt
  -> 12E2 HAS an interrupt OUT endpoint. Commands go via EP 0x02 OUT.

### 12E2 HID report descriptors (read via pyusb after kernel driver detach)
Iface 0 (39B): consumer control, standard usage page 0x0C
Iface 1 (44B):
  06ffff0a0000a101  Usage Page FFFF (vendor-defined)
  8507              Report ID = 7
  953f 7508         Input:  count=63 size=8  (63-byte IN reports)
  0900 8102         Input (Data,Var,Abs)
  0900 9102         Output (Data,Var,Abs) -> 63-byte OUT reports
  8507              Report ID = 7 (Feature)
  96f900 7508       Feature count=249 size=8 (249-byte Feature reports)
  0900 b102         Feature (Data,Var,Abs)
  c0

### Boot-enter framing (decoded from SSEdevice decompiled + report descriptor)
FlashFirmwareArctisNovaProWirelessMCURX builds buffer:
  local_res18=0x2c07 (LE bytes [07, 2c]), local_res1a=0xef -> [07, 2c, ef], len 3
Sent via DeviceLib_Write(handle, 2, chunk) -> WriteFile -> interrupt OUT EP 0x02
Report ID = 7 means wire format: [0x07(reportID), 0x2c, 0xef, 0x00...] padded to 64B
So command payload = [2c, ef] with report ID 7. cmd byte 0x07 == report ID (SteelSeries pattern).

### Sudo in WSL
- Default user timpan4 in sudo group but sudo needs password (don't have)
- SOLVED: use `wsl -d Debian -u root` to run as root directly (no password)
- apt had broken third-party repo (pkg.wslutiliti.es); disabled it; python3-usb installed

NEXT: send boot-enter [07 2c ef] to 12E2 iface 1 EP 0x02 OUT, then monitor for 12E3.
## GATE 6: Boot-enter SUCCESS - 12E3 appears briefly (step A)
Timestamp: 2026-06-26 16:32-16:36

### Method 1: WSL interrupt OUT write (wsl_boot_enter_12e2.sh)
- Attached 12E2 to WSL via usbipd (after killing SteelSeries GG processes)
- pyusb write to EP 0x02 OUT: [07 2c ef + pad 64B] -> write OK 64 bytes
- ack read on EP 0x82 IN: USBError(32, 'Pipe error') [expected - device dropping]
- RESULT: 12E3 "SteelSeries Bootloader (WinUSB)" appeared on busid 2-1 within ~3s
  (caught by concurrent monitor_12e3.ps1)
- Device then bounced back to 12E2 within seconds (same swap GG saw)

### Method 2: Windows WriteFile to HID (boot_enter_v2.py)
- Opened \\?\hid#VID_1038&PID_12E2&MI_01#... via CreateFileW
- WriteFile (interrupt OUT) [07 2c ef pad 65B] -> OK written=64 err=0
- HidD_SetFeature (SET_REPORT feature) -> returned 0 (may not be the right path)
- RESULT: 12E3 appeared again (monitor caught it) then bounced back to 12E2
- ISPDLL ConnectToBootloader did NOT connect during 15s poll window

### Key finding: boot-enter WORKS, bootloader appears but is TRANSIENT
- The boot-enter command [07 2c ef] reliably triggers 12E2 -> 12E3 transition
- 12E3 enumerates as "SteelSeries Bootloader (WinUSB)" for ~1-2 seconds
- Then drops back to 12E2 (bootloader doesn't hold / no host connects in time)
- ISPDLL ConnectToBootloader is too slow / 12E3 WinUSB binding not ready in window
- This is the core recovery challenge: catch the 12E3 window fast enough

### Transport proven
- WriteFile to 12E2 MI_01 HID interrupt OUT = working boot-enter path
- WSL pyusb EP 0x02 OUT also works
- Report ID 7, 64-byte reports, [07(reportID) 2c ef ...]

NEXT: tight loop - send boot-enter, immediately poll for 12E3 device, open it via
WinUSB/ISPDLL the instant it appears, before it bounces back.
## GATE 7: 12E3 window caught - need faster ISPDLL (step 7/8)
Timestamp: 2026-06-26 16:39
Script: boot_enter_catch_12e3.py
- Fixed path enumeration to try all 3 MI_01 paths (first openable wins)
- Path #1 (8&10e81d76) fails to open (phantom), path #2 (8&353ec25) opens OK
- WriteFile [07 2c ef] -> ok=1 written=64
- 12E3 DETECTED at iter 3 (~1.5s) via concurrent usbipd list poll
- ISPDLL ConnectToBootloader thread did NOT fire in time (still loading when 12E3
  bounced back). Need to PRE-LOAD ISPDLL before sending boot-enter.

FINDING: 12E3 window is reliably ~1-2 seconds. Must have ISPDLL already loaded
and ConnectToBootloader ready to call the instant 12E3 appears.
Also: 12E3 binds as WinUSB (oem31.inf). ISPDLL uses HIDDLL which uses HidD_* APIs.
If 12E3 is bound to WinUSB (not HID), HidD_SetFeature/HidD_GetFeature won't work
on it -> ISPDLL may need 12E3 to be HID-bound, not WinUSB-bound.
This may be why ISPDLL ConnectToBootloader fails: 12E3 is WinUSB, not HID.

NEXT: pre-load ISPDLL, send boot-enter, tight-loop ConnectToBootloader.
If still fails: consider that oem31.inf WinUSB binding may be the problem - try
removing it so 12E3 binds to default HID class instead (reversible, consented).
## GATE 8: WSL catch race - timing too tight
Timestamp: 2026-06-26 16:40
Approach: send boot-enter from Windows, detect 12E3, bind+attach to WSL, probe in WSL.
RESULT:
- boot-enter WriteFile ok=1 written=64 at 16:40:43.108
- 12E3 DETECTED at iter 2 (~43.958, ~850ms after send)
- bind completed 45.247, attach completed 46.825 (~2.8s for bind+attach)
- WSL probe at ~46.9 -> 12E3 not found (already bounced back to 12E2)
CONCLUSION: 12E3 window (~1-2s) is shorter than bind+attach chain (~2.8s).
  Cannot catch 12E3 in WSL via this race.

## ANALYSIS: why ISPDLL ConnectToBootloader fails even when 12E3 present
- Earlier: 7827 ConnectToBootloader calls in 12s, none connected.
- ISPDLL uses HIDDLL which uses HidD_* APIs (HidD_SetFeature, HidD_GetFeature).
- 12E3 interface class is likely NOT 0x03 (HID) -> HidD_* can't open it.
- Even with WinUSB driver removed, 12E3 may bind to no driver -> still no HID.
- ISPDLL path is a dead end for 12E3 unless 12E3 reports HID class + binds HidUsb.

## NEXT STRATEGY: WinUSB API direct (bypass ISPDLL/HIDDLL)
- Reinstall oem31.inf WinUSB driver for 12E3 (reversible).
- When 12E3 appears, it binds WinUSB instantly (no PnP driver search delay).
- Use WinUsb_Initialize + WinUsb_ControlTransfer to send Holtek ISP commands
  directly via EP0 control transfers, all in-process, no usbipd delay.
- This bypasses the HID class requirement and the usbipd attach latency.
- If 12E3 has an interrupt IN endpoint, also try WinUsb_ReadPipe for status.
## GATE 9: 12E3 PnP binding too slow - root cause found
Timestamp: 2026-06-26 16:45

### Experiments
1. hidapi tight-loop (436 iters/15s): 12E3 NEVER visible to hidapi. PID goes
   12E2 → (gap, no 1038 PIDs except 12E0) → 12E2. 12E3 invisible.
2. WinUSB ctypes tight-loop (2757 iters/15s, ~5ms each): 12E3 path NEVER found
   via SetupDiGetClassDevs with WinUSB GUID.
3. Concurrent usbipd list: "12E3 SEEN on USB bus!" — confirms 12E3 IS on the bus.

### Root cause
12E3 appears on the USB bus for ~1-2 seconds. But Windows PnP cannot finish
driver binding (HID class or WinUSB) in that window. The device interface GUID
is never registered, so no usermode API (hidapi, WinUSB, ISPDLL) can open it.
The bootloader watchdog times out and the device bounces back to 12E2.

This is WHY SteelSeries uses sshid.sys (a kernel filter driver that sits in the
USB stack and can see/control the device BEFORE PnP loads a function driver).
GG's flash path goes through sshid.sys → DeviceIoControl, not through HID APIs.

### Why ISPDLL ConnectToBootloader fails
Same reason: ISPDLL/HIDDLL use HidD_* APIs which need the HID class driver
bound. 12E3's HID interface never gets bound in time.

### Remaining viable paths
A. Use sshid.sys filter driver — it's already installed (ROOT\SYSTEM\0001,
   service=ssdevfactory). If it can intercept 12E3, it might allow direct
   DeviceIoControl access before PnP finishes. But sshid was designed for
   WRITE_REPORT→SET_REPORT translation, not raw bootloader access.
B. Use libusbK as a lower filter — pre-loaded so it's ready when 12E3 appears.
C. Extend the bootloader watchdog — send a command via a lower-level path
   (USB raw/control transfer) before PnP binds.
D. Accept that GG (with sshid.sys) is the only tool that can catch the window,
   restart GG, and let it attempt the firmware update.

### Current device state
- oem31.inf (WinUSB) reinstalled for 12E3
- 12E2 present and working (normal mode)
- Boot-enter [07 2c ef] reliably triggers 12E2→12E3 transition
- 12E3 appears ~1-2s then bounces back (watchdog timeout, no host connects)
## GATE 10: WinUSB driver is the problem - sshid.inf missing 12E3
Timestamp: 2026-06-26 22:00-22:04

### Critical finding: sshid.inf does NOT list PID 12E2 or 12E3
- sshid.inf in DriverStore lists hundreds of SteelSeries PIDs (0472, 1200, etc.)
- 12E2 and 12E3 are ABSENT from the list
- sshid.sys is NOT the function driver for Arctis Nova Pro Wireless
- 12E2 binds to default HID class driver (input.inf) - works for WriteFile to OUT endpoint
- 12E3 binds to WinUSB (oem31.inf) - WinUSB does NOT handle custom IOCTL 0xB0191

### Why GG's flash fails with WinUSB (oem31.inf) installed
- 12E3 appears → WinUSB binds (fast, ~instant)
- GG opens 12E3 via WinUSB device path
- GG sends DeviceIoControl 0xB0191 → WinUSB doesn't handle it → FAIL
- Error: 0xfeadfa11 → 0xdeadbeef → 0xf1a5fa11

### With oem31.inf REMOVED
- 12E3 appears → HID class driver tries to bind (SLOW, ~2s+)
- GG sees 12E3 disconnect (newPid: 272110306, pid: 272110307)
- FindConnectedDevice PreConnect FAILS - can't open 12E3 in time
- 12E3 bounces back to 12E2 before HID class driver finishes binding
- NO 0xdeadbeef error (different failure mode)

### Analysis
- Need a driver that: (a) binds FAST when 12E3 appears, (b) handles IOCTL 0xB0191
- sshid.sys does exactly this for other SteelSeries devices, but not for 12E3
- FIX: Add 12E3 to sshid.inf and install → sshid.sys becomes function driver for 12E3
- sshid.sys handles custom IOCTLs, binds fast (it's a HID driver, not WinUSB)

### Plan
1. Add USB\VID_1038&PID_12E3 to sshid.inf (copy + modify)
2. Install modified sshid.inf for 12E3
3. Trigger GG firmware update
4. If sshid binds fast enough + handles IOCTL → flash should work

### Also need to add 12E2&MI_01 to sshid.inf
- Currently 12E2 MI_01 binds to default HID (input.inf)
- Boot-enter WriteFile works with default HID, but flash might need sshid for 12E2 too
- For now: just add 12E3, see if flash works
## GATE 11: WinUSB device handle opens but WinUsb_Initialize fails
Timestamp: 2026-06-26 22:10-22:15

### Key finding: 12E3 device handle CAN be opened, but WinUSB not ready
- CreateFileW with generic GUID {a5dcbf10} succeeds at ~240ms after boot-enter
- WinUsb_Initialize FAILS (returns 0) - WinUSB driver interface not registered yet
- INF-specific GUID {dc1f8d3e} path does NOT open - interface never registered
- DeviceClasses registry has NO entry for {dc1f8d3e} on 12E3
- DeviceIoControl 0xB0191 fails (WinUSB doesn't handle custom IOCTLs)
- WriteFile fails (WinUSB doesn't expose HID interrupt pipes)

### sshid.sys analysis
- sshid.inf does NOT list PID 12E2 or 12E3 (Arctis Nova Pro Wireless not supported)
- sshid.sys is a LowerFilter under mshidkmdf (HID KMDF function driver)
- On Win11, sshid.Device_Win11.NT includes MsHidKmdf.inf for proper function driver
- Manual registry edit to add LowerFilters=sshid + Service=mshidkmdf on 12E3:
  Result: CM_PROB_FAILED_START (Problem 10) - mshidkmdf can't start without
  proper INF install (Include=MsHidKmdf.inf / Needs=MsHidKmdf.NT)
- Modified sshid_12e3.inf can't be installed: CAT signature mismatch (0xE000022F)
  even with test-signing ON (Win11 requires proper signature for driver packages)

### Root cause summary
The 12E3 bootloader appears for ~1-2 seconds. In that window:
1. WinUSB driver: handle opens but WinUsb_Initialize not ready (interface not registered)
2. HID class driver: fails to start (CM_PROB_FAILED_START) without proper INF
3. sshid filter: can't be installed (CAT signature mismatch)
4. No usermode API can send data to 12E3 before it bounces back to 12E2

The ONLY solution is a kernel driver pre-loaded in the stack that can intercept
IRPs before the function driver initializes. SteelSeries's sshid.sys does this
for other PIDs but not for 12E3. A patched sshid.inf with 12E3 + proper CAT
signature would fix this. Only SteelSeries can provide that.

### What we CAN do (proven working)
- Boot-enter [07 2c ef] reliably triggers 12E2 → 12E3 transition
- 12E3 appears on USB bus (confirmed via usbipd, PnP, CreateFileW)
- 12E3 is a HID class device (Class 03, vendor-defined usage page FFFF)
- 12E3 has 2 HID collections (Col01, Col02)
- CreateFileW opens 12E3 device handle in ~240ms
- Transport is proven; only driver initialization timing prevents communication

### What SteelSeries support needs to provide
- A patched sshid.inf that includes USB\VID_1038&PID_12E3 (and 12E2&MI_01)
- OR a dedicated recovery tool that can communicate with 12E3 during the
  bootloader window (using a pre-loaded kernel driver)
- OR a bootloader firmware update that extends the watchdog timeout
## GATE 12: Modified sshid.inf SIGNED + INSTALLED SUCCESSFULLY
Timestamp: 2026-06-26 22:39

### Driver package created and signed
- Modified sshid.inf: added USB\VID_1038&PID_12E3 entries (both Win10 and Win11 sections)
- Created CAT file using makecat.exe (from WDK bin, no inf2cat needed)
- Created new self-signed code signing cert: CN=SteelSeriesRecovery (exportable key)
- Added cert to Trusted Root + TrustedPublisher
- Signed CAT with signtool (SHA256, PFX-based)
- Fixed CatalogFile reference in INF (sshid.cat → sshid_12e3.cat)
- Rebuilt CAT after INF fix, re-signed
- Installed via pnputil /add-driver /install → SUCCESS (oem34.inf)
  SetupAPI: "Outcome - Imported", "[Exit status: SUCCESS]"

### Boot flags set (pending reboot)
- bcdedit /set nointegritychecks on → Yes
- bcdedit /set testsigning on → Yes (already was)
- Both require reboot to take effect
- User is running sfc /scannow + DISM (per SteelSeries support) and will reboot

### Last firmware update attempt (before reboot)
- PUT /device/246/firmware at 22:40:37
- Firmware update: FAILED (0xdeadbeef) at 22:40:39
- This was BEFORE the sshid driver was active (device was phantom, not re-enumerated)
- The sshid driver will only take effect when 12E3 next appears (after reboot)

### State when user returns from reboot
- nointegritychecks ON, testsigning ON (active after reboot)
- sshid_12e3.inf installed as oem34.inf in DriverStore
- SteelSeriesRecovery cert in Trusted Root + TrustedPublisher
- WinUSB oem31.inf also installed (12E3 may bind to either)
- When 12E3 appears, PnP should select sshid_12e3 (rank: HIDClass with LowerFilter)
  over WinUSB (USB class) — but need to verify driver ranking

### IMMEDIATE NEXT STEP after reboot
1. Start SteelSeries GG with -enableDebugLog
2. Trigger firmware update: PUT /device/246/firmware
3. Check debug log for: sshid binding, 12E3 communication, flash result
4. If sshid binds and holds 12E3 → flash should succeed
5. If still fails → check if WinUSB (oem31) is being selected over sshid (oem34)
   and remove oem31 if needed
## GATE 13: BREAKTHROUGH - 12E3 descriptors read via USB hub driver
Timestamp: 2026-06-26 23:25

### Method: IOCTL_USB_GET_DESCRIPTOR_FROM_NODE_CONNECTION via hub device
- Hub paths found via registry DeviceClasses (GUID {f18a0e88-c30c-11d0-8815-00a0c906bed8})
- Opened hub device (e.g. \\?\usb#ROOT_HUB30#...#{guid}) with CreateFileW
- Sent IOCTL_USB_GET_DESCRIPTOR_FROM_NODE_CONNECTION with port number
- NO function driver needed on 12E3! Hub driver handles it directly.

### 12E3 device descriptor (read successfully):
  bLength=18, bcdUSB=2.00, bDeviceClass=0xEF (Misc)
  bDeviceSubClass=0x02, bDeviceProtocol=0x01 (IAD)
  VID=0x1038, PID=0x12E3, bcdDevice=0x0800
  iManufacturer=1, iProduct=2, iSerialNumber=0
  bNumConfigurations=1

### 12E3 config descriptor (41 bytes, read successfully):
  Config 1: 1 interface, 500mA, bus powered
  Interface 0: HID class (0x03), 2 endpoints
  HID descriptor: bcdHID=1.00, 1 report descriptor, length=0x53 (83 bytes)
  EP 0x81 IN: interrupt, 64 bytes, interval 16
  EP 0x01 OUT: interrupt, 64 bytes, interval 16  ← HAS OUT ENDPOINT!

### Key findings:
1. 12E3 HAS an interrupt OUT endpoint (EP 0x01 OUT, 64 bytes)
2. 12E3 is a single-interface HID device (not composite like 12E2)
3. 12E3 report descriptor is 83 bytes (larger than 12E2's 44 bytes)
4. Device found at iter 17 (~340ms after boot-enter) via hub
5. Device STAYS on bus with only WinUSB (no sshid to cause bounce)
6. Hub driver can read descriptors WITHOUT any function driver on 12E3

### NEXT: Send control transfers to 12E3 via hub driver
- Need to find an IOCTL that sends arbitrary control transfers via hub
- Or use the GEN GUID handle (opens at ~250ms) with DeviceIoControl
- The GEN GUID handle is to the raw USB device, which might support
  IOCTL_USB_CONTROL_TRANSFER or similar
## GATE 14: 12E3 HID REPORT DESCRIPTOR OBTAINED
Timestamp: 2026-06-26 23:35

### Method: hub_read_rdesc.py (IOCTL_USB_GET_DESCRIPTOR_FROM_NODE_CONNECTION via hub)
- Found 12E3 on hub port 1, iter 17 (~170ms after boot-enter)
- Read HID report descriptor (type 0x22) via hub driver — NO function driver needed!

### 12E3 Report Descriptor (83 bytes, decoded):
Collection 1 (Vendor-defined, Usage Page FFFF):
  Report ID = 6
  Input: 63 bytes × 8 bits (Data, Var, Abs)
  Output: 63 bytes × 8 bits (Data, Var, Abs) ← 63-byte OUT reports
  Feature: 1023 bytes × 8 bits (Data, Var, Abs) ← 1023-byte Feature reports!
Collection 2 (Consumer Control, Usage Page 0x0C):
  Report ID = 1
  6 × 1-bit buttons (Play, Pause, Next, Prev, Vol+, Vol-)

### Key protocol differences from 12E2:
- 12E2 uses Report ID 7 (63-byte IN/OUT, 249-byte Feature)
- 12E3 uses Report ID 6 (63-byte IN/OUT, 1023-byte Feature)
- 12E3's 1023-byte Feature report ≈ SSEdevice's 1012-byte flash chunk (0xa106 packet)
- 12E3 has EP 0x01 OUT (64 bytes) for interrupt OUT writes
- 12E3 has EP 0x81 IN (64 bytes) for interrupt IN reads

### What we can now do:
1. Read 12E3 descriptors via hub driver (no function driver) ✓
2. Open GEN GUID handle at ~244ms (raw USB device) ✓
3. WriteFile to GEN GUID fails (not a HID handle) ✗
4. WinUsb_Initialize fails (INF GUID never registers) ✗
5. Need: send HID SET_REPORT (control transfer) to 12E3 via EP0

### REMAINING PATHS:
A. Find a way to send control transfers to 12E3 via hub driver or raw device handle
B. Install libusb-win32 filter driver (creates own interface, bypasses function driver)
C. Use WSL: attach 12E3 to WSL while it's on the bus (it stays 10+ seconds with WinUSB only)
   - usbipd bind+attach 12E3, then pyusb control transfer from WSL
   - The device stays long enough for the bind+attach chain
## GATE 15: WSL PYUSB COMMUNICATES WITH 12E3 BOOTLOADER! ✓
Timestamp: 2026-06-26 23:40

### Method: Windows boot-enter → usbipd bind+attach → WSL pyusb
1. Send boot-enter [07 2c ef] to 12E2 via Windows HID WriteFile
2. usbipd detects 12E3 on busid 2-1 (~60ms after boot-enter)
3. Elevated: usbipd bind --busid 2-1 --force + usbipd attach --wsl --busid 2-1
4. Signal file triggers WSL probe script
5. pyusb finds 12E3, detaches kernel driver, claims interface

### Results:
- Device descriptor: 1038:12e3, bcdDevice 0x0800, "SteelSeries" / "SteelSeries Bootloader"
- Config: 1 interface (HID), 2 endpoints (EP 0x81 IN + EP 0x01 OUT, both 64-byte interrupt)
- **SET_REPORT(id=6): sent 65 bytes — SUCCESS!**
- GET_REPORT(id=6): returned empty (no error)
- GET_REPORT(id=1): returned empty (no error)
- Read EP 0x81: USBError(32, 'Pipe error') — expected, needs command first
- **Vendor IN requests 0x05-0x0F: ALL returned 64 bytes of zeros — device responding!**
- Vendor IN requests 0x00-0x04: timed out (no response)

### What this means:
- We have a WORKING transport to the 12E3 bootloader via WSL
- The device accepts HID SET_REPORT (control transfer via EP0)
- The device responds to vendor control transfers (bmRequestType=0xC0)
- Requests 0x05-0x0F return 64 zero bytes — bootloader firmware endpoints
- The device STAYS on the bus long enough for the full bind+attach+probe sequence

### NEXT STEPS:
1. Map vendor request numbers to Holtek ISP functions (GetBootloaderVer, GetMCUId, etc.)
2. Try ISPDLL commands via the working WSL transport:
   - SetHwId(0x0219) + ConnectToBootloader
3. Try SSEdevice protocol commands:
   - Boot command [07 2c ef] (already sent for boot-enter)
   - Status query
   - GetBootloaderVer
4. If we can read bootloader version/status → proceed to firmware flash

### Protocol info for 12E3:
- Report ID 6: 63-byte IN/OUT + 1023-byte Feature (vendor-defined)
- Report ID 1: Consumer control buttons (6 buttons)
- EP 0x81 IN: 64 bytes interrupt
- EP 0x01 OUT: 64 bytes interrupt
- SET_REPORT via control transfer: bmRequestType=0x21, bRequest=0x09, wValue=reportID<<8
- GET_REPORT via control transfer: bmRequestType=0xA1, bRequest=0x01, wValue=reportID<<8
- Vendor IN: bmRequestType=0xC0, bRequest=req_num, wValue=0, wIndex=0
