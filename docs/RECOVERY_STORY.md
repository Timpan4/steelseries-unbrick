# The Great SteelSeries Arctis Nova Pro Wireless Unbricking

> A reverse-engineering saga: 7 sessions, 15+ gates, 1 bootloader handshake, and no public tool I could find for this specific recovery path.
> Outcome: **headset fully recovered from a bricked state, firmware reflashed, system restored to clean.**

---

## The Victim

**SteelSeries Arctis Nova Pro Wireless** — flagship gaming headset, dual-wireless (2.4GHz + Bluetooth).

**Symptom:** Both white and blue lights blink simultaneously on power-on. Both radios trapped in pairing mode. Headset unusable.

**Root cause (eventually proven):** The RX MCU firmware crashed into a frozen bootloader state. SteelSeries GG could detect the headset in normal mode (PID 12E2) but could not read its firmware version (`0xfead7007` ReadFile timeout), and could not complete a firmware update — the bootloader device (PID 12E3) appeared for only 1-2 seconds before bouncing back, and no Windows API could open it in time.

---

## The Tools We Built (From Nothing)

I could not find a public tool that could flash this Arctis Nova Pro Wireless RX MCU bootloader path. For this one-device recovery, we had to build the missing pieces:

### Reverse Engineering
- **Ghidra decompilation** of `SSEdevice.dll` (2,389 functions), `sshid.sys` (156 functions), `ISPDLL.dll`, `HIDDLL.dll`
- Full flash protocol decoded from `FlashFirmwareArctisNovaProWirelessMCU` and `PrepareDeviceArctisNovaProWireless`
- Intel HEX firmware parser (Python)
- CRC32 flash packet builder (standard reflected, poly `0xEDB88320`)

### USB Transport
- **usbipd-win 5.3.0** — Windows-to-WSL USB bridge
- **WSL2 Debian** with `python3-usb` (pyusb) for raw USB control transfers
- **Windows HID WriteFile** (ctypes) for boot-enter command delivery
- Hub driver IOCTL probe for reading 12E3 descriptors without a function driver

### Driver Experiments (installed then cleaned up)
- Self-signed `SteelSeriesRecovery` certificate (CN, PFX, CAT)
- Modified `sshid_12e3.inf` with 12E3 PID entries (signed, installed as oem34)
- WinUSB driver for 12E3 (oem31)
- libusb-win32 filter driver for 12E3
- Test-signing + nointegritychecks boot flags

---

## The Protocol (Fully Decoded)

### Device Map
| PID | Device | Mode |
|-----|--------|------|
| 12E0 | Base station | Always present, composite USB |
| 12E2 | Headset (normal) | Composite: MI_00 consumer control + MI_01 vendor HID |
| 12E3 | SteelSeries Bootloader | Appears only during firmware update (1-2s watchdog) |

### Boot-Enter Command (12E2 -> 12E3)
```
Target: 12E2 MI_01 (vendor-defined HID, Usage Page 0xFFFF)
Report ID: 7 (63-byte OUT reports)
Wire: [0x07, 0x2C, 0xEF, 0x00...] padded to 64 bytes
Transport: WriteFile to HID interrupt OUT endpoint (EP 0x02)
```

### Bootloader Handshake (the breakthrough)
```
Target: 12E3 (SteelSeries Bootloader, PID 0x12E3)
Report ID: 6 (1023-byte feature reports!)
Command: 0xB006 = [0x06, 0xB0]
Transport: SET_REPORT feature (control transfer, bmRequestType=0x21, bRequest=0x09)
Ack: EP 0x81 interrupt IN, 64 bytes: ack[0]==0x06 = SUCCESS
```
**This handshake was the missing piece.** Found in `PrepareDeviceArctisNovaProWireless` at offset `0x18002F370` — it sends `0xB006` right after 12E3 enumerates, before any flash writes. Without it, the bootloader returns zeros to everything.

### Flash Packet (0xA106)
```
Layout (1024 bytes, sent as 1023-byte feature report + 1 report ID byte):
  Offset 0:    0x06         (HID report ID)
  Offset 1:    0xA1         (flash command, little-endian 0xA106)
  Offset 2-5:  address      (4 bytes, big-endian)
  Offset 6-7:  size         (2 bytes, big-endian, max 0x3F4 = 1012)
  Offset 8-11: CRC32        (4 bytes, big-endian, zlib.crc32 of data)
  Offset 12+:  data         (up to 1012 bytes)
Transport: SET_REPORT feature (report ID 6)
Ack: EP 0x81: ack[0]==0x06 success, ack[1]==0x01 fail
```

### Reset Command
```
Command: 0xBB06 = [0x06, 0xBB]
Transport: SET_REPORT feature (report ID 6)
Effect: device resets from 12E3 bootloader back to 12E2 normal mode
```

### 12E3 HID Report Descriptor (83 bytes, decoded)
```
Collection 1 (Vendor-defined, Usage Page 0xFFFF):
  Report ID 6: 63-byte Input + 63-byte Output + 1023-byte Feature
Collection 2 (Consumer Control):
  Report ID 1: 6 buttons
```

### 12E2 HID Report Descriptor (Iface 1, 44 bytes)
```
Vendor-defined, Usage Page 0xFFFF:
  Report ID 7: 63-byte Input + 63-byte Output + 249-byte Feature
```

---

## The 15 Gates

Every approach was tested, proven, and documented with evidence.

### Gate 1: PnP Classification + usbipd + DLL Exports + Packet Framing
- **PnP:** 12E3 and Holtek ISP device (04D9:8008) are PHANTOM (disconnected). Only 12E0/12E2 present.
- **usbipd:** Not installed (no WSL USB bridge).
- **ISPDLL/HIDDLL:** x64, 29 + 19 exports, callable via ctypes.
- **Packet framing:** 0xA106 flash packet decoded from decompiled code.

### Gate 2: ISPDLL Connect Probe
- `SetHwId(0x0219)` + `ConnectToBootloader()` -> returns -1 (FAIL).
- No bootloader device on the bus. Transport is ready; no target exists.

### Gate 3: GG Engine Log Analysis
- `ReadFirmwareVersion` on 12E2 -> `0xfead7007` (ReadFile timeout). Normal mode is also broken.
- `WriteToDevice(0x103812e3, ...)` -> `0xdeadbeef` / `0xf1a5fa11`. Flash writes target 12E3 but fail.
- Device swap detected: 272110306 (12E2) <-> 272110307 (12E3). PreConnect fails.

### Gate 4: Online Research
- **fwupd SteelSeries plugin:** Supports Stratus Duo, Aerox 3, Nova 5/3P. Does NOT cover Nova Pro Wireless.
- **HeadsetControl, Arctis Sound Manager, nova-chatmix-linux, GGWP:** NONE implement firmware flashing.
- **Holtek ISP:** No public recovery tool bypasses needing the MCU already in ISP mode.
- Conclusion from the tools I checked: I could not find an existing public tool that reflashes the Nova Pro Wireless RX MCU path.

### Gate 5: usbipd-win Install + WSL + 12E2 Descriptor
- usbipd-win 5.3.0 installed. 12E2 busid = 2-1.
- 12E2 has interrupt OUT endpoint (EP 0x02, 64 bytes) on MI_01.
- Boot-enter framing decoded: `[07, 2c, ef]` via report ID 7.

### Gate 6: Boot-Enter SUCCESS
- WriteFile `[07, 2c, ef]` to 12E2 MI_01 -> 12E3 appears within ~3s.
- 12E3 bounces back to 12E2 in 1-2 seconds (bootloader watchdog).
- ISPDLL ConnectToBootloader too slow to catch the window.

### Gate 7: Catch Race
- 12E3 detected at ~1.5s. ISPDLL not loaded fast enough.
- Discovery: 12E3 binds as WinUSB (oem31). ISPDLL uses HidD_* APIs -> can't open WinUSB device.

### Gate 8: WSL Catch Race
- boot-enter -> detect 12E3 -> bind+attach to WSL: 2.8s total.
- 12E3 window is ~1-2s. Bind+attach too slow.

### Gate 9: PnP Binding Too Slow (Root Cause Found)
- hidapi tight-loop: 436 iters/15s. 12E3 NEVER visible.
- WinUSB ctypes tight-loop: 2757 iters/15s. 12E3 path NEVER found.
- usbipd list: 12E3 IS on the bus.
- **Root cause:** Windows PnP cannot finish driver binding in 1-2 seconds. No usermode API can open 12E3 before it bounces.

### Gate 10: sshid.inf Missing 12E3
- `sshid.inf` lists hundreds of SteelSeries PIDs but 12E2 and 12E3 are ABSENT.
- With WinUSB: `0xdeadbeef` (IOCTL 0xB0191 not handled).
- Without WinUSB: `FindConnectedDevice PreConnect` fails (HID class driver too slow).

### Gate 11: WinUsb_Initialize Fails
- CreateFileW with generic GUID opens 12E3 at ~240ms.
- WinUsb_Initialize FAILS (interface not registered yet).
- Modified sshid_12e3.inf: CAT signature mismatch (0xE000022F).
- Manual LowerFilters registry edit: CM_PROB_FAILED_START.

### Gate 12: Modified sshid.inf Signed + Installed
- Created sshid_12e3.inf with 12E3 entries.
- Signed CAT with self-signed SteelSeriesRecovery cert.
- Installed as oem34.inf: SUCCESS.
- testsigning + nointegritychecks ON (pending reboot).

### Gate 13: BREAKTHROUGH - Hub Driver Reads 12E3 Descriptors
- `IOCTL_USB_GET_DESCRIPTOR_FROM_NODE_CONNECTION` via hub device.
- NO function driver needed! Hub driver reads descriptors directly.
- 12E3 device descriptor: bDeviceClass=0xEF (Misc/IAD), VID=1038, PID=12E3.
- 12E3 config: 1 HID interface, EP 0x81 IN (64B) + EP 0x01 OUT (64B).
- 12E3 report descriptor: Report ID 6, 63-byte I/O + 1023-byte Feature.

### Gate 14: Full Report Descriptor
- 12E3 uses Report ID 6 (not 7 like 12E2).
- 1023-byte feature report matches the 1012-byte flash chunk + 12-byte header.
- The 12E3 transport path is now fully understood.

### Gate 15: WSL Pyusb Communicates with Bootloader
- Boot-enter from Windows -> usbipd bind+attach -> WSL pyusb.
- SET_REPORT(id=6) succeeded. Vendor IN requests 0x05-0x0F returned 64 bytes.
- Device responds to control transfers.
- **BUT:** only got zeros back because the 0xB006 handshake was never sent.

### Gate 16 (final): The Handshake + Full Flash
- Decoded `PrepareDeviceArctisNovaProWireless`: sends `0xB006` handshake after 12E3 appears.
- Non-destructive probe: sent handshake -> got `06 b0` ack (SUCCESS). Sent size=0 flash packet -> got `06 a1 03` ack (SUCCESS).
- **Full flash:** 211 chunks, 209,712 bytes, 10.3 seconds, zero failures.
- Reset command sent. Device came back as 12E2 normal mode, all PnP interfaces OK.
- **HEADSET RECOVERED.**

---

## The Flash (Final Run)

```
Firmware: firmware_arctis_nova_pro_wireless_rx_mcu_v1.22.11.hex (590KB Intel HEX)
Parsed: 7 segments, 209,712 bytes, 211 chunks

Segments:
  seg 0: addr=0x000A00 len=444
  seg 1: addr=0x0067F0 len=38,928
  seg 2: addr=0x010000 len=56,408
  seg 3: addr=0x022800 len=55,296
  seg 4: addr=0x030000 len=9,156
  seg 5: addr=0x032C00 len=15,876
  seg 6: addr=0x036C00 len=33,604

Transport chain:
  Windows: WriteFile [07 2c ef] to 12E2 MI_01 (boot-enter)
  Windows: usbipd attach --wsl Debian --busid 2-1
  WSL:     pyusb SET_REPORT feature (0xB006 handshake)
  WSL:     pyusb SET_REPORT feature (0xA106 flash chunks x211)
  WSL:     pyusb read EP 0x81 (ack per chunk)
  WSL:     pyusb SET_REPORT feature (0xBB06 reset)

Result: 211/211 chunks, 0 failures, 209,712 bytes in 10.3s
```

---

## Why SteelSeries GG Couldn't Do It

1. **`requiresFwUpgrade` bug:** The frontend checks device 245 (base station) instead of 246 (headset), so the firmware update banner never appears.
2. **sshid.inf gap:** The `sshid.sys` filter driver doesn't list PID 12E2 or 12E3. For other SteelSeries devices, sshid intercepts IOCTLs before PnP loads a function driver — but the Nova Pro Wireless was left out.
3. **Bootloader watchdog:** 12E3 appears for only 1-2 seconds. Windows PnP can't bind a driver in time. Without sshid in the stack, no API can open the device before it bounces.
4. **No manual flash path:** GG has no "force firmware update" button. The only trigger is the frontend `requiresFwUpgrade` check, which is broken.

---

## Error Code Reference (decoded)

| Code | Meaning |
|------|---------|
| `0x3F17FA11` | WriteFile failed |
| `0xFEAD7007` | ReadFile timeout (WAIT_TIMEOUT=0x102) |
| `0xFEADFA11` | ReadFile error |
| `0xDEADBEEF` | PrepareDevice or flash write failed |
| `0xF1A5FA11` | HandleSSECmd wrapping flash failure |
| `0xCA11FA11` | DeviceIoControl 0xC0DE0038 failed |
| `0x9E9FA11` | No firmware data loaded |
| `0xBADDA7A` | Flash ack returned 0x02 or 0x03 (error state) |

---

## System State After Cleanup

| Item | Status |
|------|--------|
| oem34.inf (libusb0_12e3) | Removed |
| SteelSeriesRecovery cert | Removed from Trusted Root + TrustedPublisher |
| testsigning | OFF (effective after reboot) |
| nointegritychecks | OFF (effective after reboot) |
| usbipd bind/detach for 2-1 | Cleaned |
| WSL background job | Stopped, WSL shut down |
| PFX, sshid package, libusb files | Deleted |
| Phantom PnP nodes (21 stale 12E2/12E3) | Removed |
| Headset | Working (12E2 normal mode, firmware v1.22.11) |

**One reboot needed** to finalize bcdedit changes (testsigning/nointegritychecks).

---

## Key Files (preserved on desktop)

```
C:\Users\timpa\Desktop\steelseries_firmware_backup\
  272110306\
    firmware_arctis_nova_pro_wireless_rx_mcu_v1.22.11.hex   (flashed firmware)
    firmware_arctis_nova_pro_wireless_rx_bt_v1.15.4.bin      (BT firmware, not flashed)
  usb_only_work\
    wsl_flash_rx.py          (the flash script that worked)
    wsl_probe_v3.py          (non-destructive probe with handshake)
    send_boot_enter_only.py  (boot-enter via HID WriteFile)
    run_flash.ps1            (elevated orchestrator)
    USB_ONLY_RECOVERY_JOURNAL.md  (gate-by-gate evidence log)
  cleanup.ps1                (system cleanup script)
  cleanup.log                (cleanup verification)
C:\Users\timpa\AppData\Local\Temp\
    sedevice_decompiled.c     (SSEdevice.dll full decompilation)
    headset_handoff.md        (original handoff document)
```

---

## Timeline

| Session | What happened |
|---------|---------------|
| Thread 019f004e | Initial troubleshooting: white+blue blink, USB bypass trick, factory reset |
| Thread 019f02f9 | Reverse engineering begins: SSEdevice.dll, sshid.sys, Ghidra decompilation |
| Thread 019f0309 | Frontend bug found (requiresFwUpgrade checks wrong device) |
| Thread 019f030f | Engine API attempt, WinUSB driver, HID API, IAT hooks — all fail |
| Thread 019f00bf | ISPDLL path, version.json bump, sshid.inf analysis |
| Thread 019f02cd | Random black screen + fans 100% investigation (unrelated) |
| Thread 019f02f5 | Modified sshid.inf signed + installed, bcdedit flags set |
| Thread 019f030d | Reboot retry: same 0xdeadbeef, then PreConnect failure mode |
| Thread 019f0443 | Hub driver descriptors, WSL pyusb, report descriptor decoded |
| Thread 019f07e5 | **Handshake found, non-destructive probe SUCCESS, full flash SUCCESS** |

---

## Lessons

1. **Read the decompiled code carefully.** The `0xB006` handshake was in `PrepareDeviceArctisNovaProWireless` the whole time. Every prior probe skipped `PrepareDevice` and went straight to flash commands — so the bootloader never unlocked.

2. **The hub driver can read USB descriptors without a function driver.** `IOCTL_USB_GET_DESCRIPTOR_FROM_NODE_CONNECTION` works on the hub's port, not the device. This let us read 12E3's full report descriptor while no driver was bound.

3. **usbipd + WSL + pyusb is a legitimate USB debugging tool.** It gives you raw control transfers from Linux while the device is physically on Windows. The 2.8s bind+attach latency was the only obstacle — solved by the device staying on the bus long enough once WinUSB was the only driver.

4. **Test-signing + self-signed certs work for driver installation** on Windows 11 with testsigning ON and Secure Boot OFF. The CAT signature was accepted, the driver installed, and PnP loaded it. (It still didn't help because the 1-2s watchdog was too short, but the mechanism worked.)

5. **No public tool found for this exact path.** I could not find a public tool that flashes this Arctis Nova Pro Wireless RX MCU bootloader path, so this should be framed as a first-known, one-device validated recovery rather than an absolute claim about every private or obscure tool.


---

## Authorship Note

This recovery was performed and validated on real hardware by Timpan4, but the scripts,
reverse-engineering writeups, and documentation were made together with GLM 5.2. The
human role was primarily prompting, running experiments, supplying logs/device access,
validating the final flash, and choosing what to publish.
