param(
  [string]$BusId = "2-1",
  [string]$WslDistro = "Debian",
  [string]$WorkDir = "C:\Users\timpa\Desktop\steelseries_firmware_backup\usb_only_work",
  [string]$Firmware = "C:\Users\timpa\Desktop\steelseries_firmware_backup\272110306\firmware_arctis_nova_pro_wireless_rx_mcu_v1.22.11.hex",
  [string]$LogPath = "C:\Users\timpa\Desktop\steelseries_firmware_backup\usb_only_work\flash_run.log"
)

$env:Path = "C:\Program Files\usbipd-win;" + $env:Path
$log = $LogPath
Remove-Item $log -ErrorAction SilentlyContinue
function Log($m){ $ts=Get-Date -Format "HH:mm:ss.fff"; Add-Content $log "$ts $m"; Write-Output "$ts $m" }
Log "=== START ==="
# Clean prior usbipd state on the selected bus ID
usbipd unbind --busid $BusId 2>&1 | Out-Null
usbipd detach --busid $BusId 2>&1 | Out-Null
Start-Sleep -Milliseconds 800
Log "usbipd state cleared"
Get-Process | Where-Object { $_.ProcessName -match 'steel' } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 600
Log "GG killed"
Log "boot-enter..."
python (Join-Path $WorkDir "send_boot_enter_only.py") 2>&1 | ForEach-Object { Log "be: $_" }
Log "poll 12E3 + attach..."
$found=$false
for ($i=0; $i -lt 120; $i++) {
  $out = usbipd list 2>&1
  if ($out -match '12e3') {
    Log "12E3 SEEN iter $i"
    $found=$true
    # attach directly (persisted bind may exist)
    $a = usbipd attach --wsl $WslDistro --busid $BusId 2>&1
    Log "attach: $a"
    if ($a -notmatch 'attached' -and $a -notmatch 'success') {
      Log "attach retry w/ bind..."
      usbipd bind --busid $BusId --force 2>&1 | ForEach-Object { Log "bind: $_" }
      $a2 = usbipd attach --wsl $WslDistro --busid $BusId 2>&1
      Log "attach2: $a2"
    }
    break
  }
  Start-Sleep -Milliseconds 50
}
if (-not $found) { Log "12E3 NOT seen"; Log "=== END ==="; exit 1 }
Log "running WSL flash..."
$wslScript = wsl -d $WslDistro -u root -- wslpath -a (Join-Path $WorkDir "wsl_flash_rx.py")
$wslFirmware = wsl -d $WslDistro -u root -- wslpath -a $Firmware
wsl -d $WslDistro -u root -- python3 $wslScript $wslFirmware 2>&1 | ForEach-Object { Log "wsl: $_" }
Log "=== END ==="
