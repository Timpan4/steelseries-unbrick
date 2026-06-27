# SteelSeries Arctis Nova Pro Wireless - Firmware Recovery Tools

Tools and documentation for reflashing a bricked SteelSeries Arctis Nova Pro Wireless headset
when SteelSeries GG cannot perform the update.

This is the result of a full reverse-engineering effort that decompiled SteelSeries's
`SSEdevice.dll`, decoded the bootloader flash protocol, and built a working flasher
from scratch. **No public tool existed that could flash a SteelSeries headset MCU.**

## The Problem

The Arctis Nova Pro Wireless can brick into a state where both white and blue lights
blink simultaneously (both radios trapped in pairing mode). SteelSeries GG fails to
recover it because:

1. **`requiresFwUpgrade` frontend bug** — checks device 245 (base station) instead of
   246 (headset), so the firmware update banner never appears
2. **`sshid.inf` gap** — the SteelSeries HID filter driver doesn't list PID 12E2 or
   12E3, so it can't intercept bootloader IOCTLs during the 1-2 second watchdog window
3. **Bootloader watchdog** — the bootloader device (12E3) appears for only 1-2 seconds
   before bouncing back to normal mode, and Windows PnP can't bind a driver in time

## The Solution

A three-stage flash protocol:

1. **Boot-enter** — send `[07 2C EF]` to the headset's normal-mode HID interface (12E2)
   via `WriteFile` to trigger bootloader mode (12E3)
2. **USB bridge** — attach 12E3 to WSL via `usbipd-win`, then use `pyusb` for raw USB
   control transfers
3. **Flash** — send the `0xB006` handshake to unlock the bootloader, then stream
   `0xA106` flash packets (address + size + CRC32 + data) as 1023-byte HID feature
   reports, reading an ack per chunk on EP 0x81

## The Breakthrough

The `0xB006` handshake command. Found by decompiling `PrepareDeviceArctisNovaProWireless`
in `SSEdevice.dll` — it sends this command right after the bootloader enumerates, before
any flash writes. Without it, the bootloader returns zeros to everything. **Every prior
attempt failed because this handshake was never sent.**

## Protocol Reference

### Device Map
| PID | Device | Mode |
|-----|--------|------|
| `12E0` | Base station | Always present, composite USB |
| `12E2` | Headset (normal) | Composite: MI_00 consumer control + MI_01 vendor HID |
| `12E3` | SteelSeries Bootloader | Appears only during firmware update (1-2s watchdog) |

### Commands
| Command | Bytes | Target | Transport | Purpose |
|---------|-------|--------|-----------|---------|
| Boot-enter | `07 2C EF` | 12E2 MI_01 | HID WriteFile (report ID 7) | Trigger 12E2 -> 12E3 transition |
| Handshake | `06 B0` | 12E3 | SET_REPORT feature (report ID 6) | Unlock bootloader for flash |
| Flash | `06 A1` + addr(4 BE) + size(2 BE) + crc32(4 BE) + data(<=1012) | 12E3 | SET_REPORT feature (report ID 6) | Write firmware chunk |
| Reset | `06 BB` | 12E3 | SET_REPORT feature (report ID 6) | Reset to normal mode |

### Ack Format (EP 0x81, 64 bytes)
| Byte | Value | Meaning |
|------|-------|---------|
| 0 | `0x06` | Success |
| 0 | other | Failure |
| 1 | `0x01` | Write failed |
| 1 | `0x02` / `0x03` | Error state (`0xBADDA7A`) |

## Requirements

- **Windows 11** with admin privileges
- **WSL2** (Debian or Ubuntu) with `python3-usb` installed
- **usbipd-win** 5.x (`winget install dorssel.usbipd-win`)
- **Python 3** on Windows (for the boot-enter script)
- **Firmware file** — Intel HEX format for the RX MCU

## Usage

### 1. Install dependencies

```powershell
# Windows: usbipd-win
winget install dorssel.usbipd-win

# WSL: pyusb
wsl -d Debian -u root -- apt install -y python3-usb
```

### 2. Non-destructive probe (test communication)

Verify the bootloader responds before attempting a flash:

```powershell
# Edit run_probe.ps1 to set your paths, then run elevated:
powershell -ExecutionPolicy Bypass -File scripts\run_probe.ps1
```

Expected output: `handshake OK: 06b0...` and `Flash packet ... ack=06a1...`

### 3. Flash the firmware

```powershell
# Edit wsl_flash_rx.py to set FIRMWARE path, then run elevated:
powershell -ExecutionPolicy Bypass -File scripts\run_flash.ps1
```

The script will:
1. Kill SteelSeries GG (to free the HID device)
2. Send boot-enter to trigger bootloader mode
3. Attach the bootloader to WSL via usbipd
4. Send the handshake, stream flash chunks with CRC32, verify each ack
5. Send reset command

### 4. Cleanup

After a successful flash, clean up any temporary system changes:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\cleanup.ps1
```

## Files

```
scripts/
  wsl_flash_rx.py          # Flash script: parses Intel HEX, sends 0xA106 chunks, verifies acks
  wsl_probe_v3.py          # Non-destructive probe: sends handshake + size=0 packet
  send_boot_enter_only.py  # Sends [07 2C EF] to 12E2 via HID WriteFile
  run_flash.ps1            # Elevated orchestrator: boot-enter + attach + flash
  run_probe.ps1            # Elevated orchestrator: boot-enter + attach + probe
  cleanup.ps1              # Removes drivers, certs, boot flags

docs/
  RECOVERY_STORY.md              # Full narrative of the recovery (16 gates)
  USB_ONLY_RECOVERY_JOURNAL.md   # Gate-by-gate evidence log with timestamps
```

## Warning

**This writes firmware to your headset's MCU.** A failed flash can leave the device in
a worse state. The scripts verify every chunk ack and abort cleanly on failure, but
there is inherent risk. Use at your own risk.

## Credits

Reverse-engineered and built by [Timpan4](https://github.com/Timpan4).

## License

MIT — see [LICENSE](LICENSE).
