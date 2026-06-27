# === SYSTEM CLEANUP SCRIPT ===
$env:Path = "C:\Program Files\usbipd-win;" + $env:Path
$log = "C:\Users\timpa\Desktop\steelseries_firmware_backup\cleanup.log"
function Log($m){ $ts=Get-Date -Format "HH:mm:ss.fff"; Add-Content $log "$ts $m"; Write-Output "$ts $m" }
Remove-Item $log -ErrorAction SilentlyContinue
Log "=== CLEANUP START ==="

# 1. Remove libusb0_12e3 driver (oem34.inf)
Log "removing oem34.inf (libusb0_12e3)..."
$r = pnputil /delete-driver oem34.inf /uninstall /force 2>&1
Log "oem34: $r"

# 2. Remove SteelSeriesRecovery cert from Trusted Root
Log "removing cert from TrustedRoot..."
$cert = Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.Subject -match "SteelSeriesRecovery" }
if ($cert) {
    $r = Remove-Item "Cert:\LocalMachine\Root\$($cert.Thumbprint)" -Force 2>&1
    Log "Root cert removed: $r"
} else { Log "no cert in TrustedRoot" }

# 3. Remove cert from TrustedPublisher
Log "removing cert from TrustedPublisher..."
$cert2 = Get-ChildItem Cert:\LocalMachine\TrustedPublisher | Where-Object { $_.Subject -match "SteelSeriesRecovery" }
if ($cert2) {
    $r = Remove-Item "Cert:\LocalMachine\TrustedPublisher\$($cert2.Thumbprint)" -Force 2>&1
    Log "TrustedPublisher cert removed: $r"
} else { Log "no cert in TrustedPublisher" }

# 4. Disable test-signing
Log "disabling testsigning..."
$r = bcdedit /set testsigning off 2>&1
Log "testsigning: $r"

# 5. Disable nointegritychecks
Log "disabling nointegritychecks..."
$r = bcdedit /set nointegritychecks off 2>&1
Log "nointegritychecks: $r"

# 6. Detach/unbind usbipd 2-1
Log "cleaning usbipd 2-1..."
usbipd detach --busid 2-1 2>&1 | Out-Null
usbipd unbind --busid 2-1 2>&1 | Out-Null
Log "usbipd cleaned"

# 7. Remove the PFX file
Log "removing PFX..."
Remove-Item "C:\Users\timpa\Desktop\steelseries_firmware_backup\usb_only_work\SteelSeriesRecovery.pfx" -Force -ErrorAction SilentlyContinue
Log "PFX removed"

# 8. Remove the signed sshid_12e3 package
Log "removing sshid_12e3 package..."
Remove-Item "C:\Users\timpa\Desktop\steelseries_firmware_backup\usb_only_work\sshid_12e3_pkg" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "C:\Users\timpa\Desktop\steelseries_firmware_backup\usb_only_work\sshid_12e3.cat" -Force -ErrorAction SilentlyContinue
Remove-Item "C:\Users\timpa\Desktop\steelseries_firmware_backup\usb_only_work\sshid_12e3.inf" -Force -ErrorAction SilentlyContinue
Remove-Item "C:\Users\timpa\Desktop\steelseries_firmware_backup\usb_only_work\sshid.sys" -Force -ErrorAction SilentlyContinue
Log "sshid package removed"

# 9. Remove libusb-win32 download
Log "removing libusb-win32 zip..."
Remove-Item "C:\Users\timpa\Desktop\steelseries_firmware_backup\usb_only_work\libusb-win32.zip" -Force -ErrorAction SilentlyContinue
Remove-Item "C:\Users\timpa\Desktop\steelseries_firmware_backup\usb_only_work\libusb-win32" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "C:\Users\timpa\Desktop\steelseries_firmware_backup\usb_only_work\libusb0_12e3.inf" -Force -ErrorAction SilentlyContinue
Log "libusb removed"

Log "=== CLEANUP DONE (reboot needed for bcdedit) ==="
