$env:Path = "C:\Program Files\usbipd-win;" + $env:Path
$log = "C:\Users\timpa\Desktop\steelseries_firmware_backup\usb_only_work\probe_run.log"
Remove-Item $log -ErrorAction SilentlyContinue
function Log($m){ $ts=Get-Date -Format "HH:mm:ss.fff"; Add-Content $log "$ts $m"; Write-Output "$ts $m" }
Log "=== START ==="
# Clean prior usbipd state on 2-1
usbipd unbind --busid 2-1 2>&1 | Out-Null
usbipd detach --busid 2-1 2>&1 | Out-Null
Start-Sleep -Milliseconds 800
Log "usbipd state cleared"
Get-Process | Where-Object { $_.ProcessName -match 'steel' } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 600
Log "GG killed"
Log "boot-enter..."
python "C:\Users\timpa\Desktop\steelseries_firmware_backup\usb_only_work\send_boot_enter_only.py" 2>&1 | ForEach-Object { Log "be: $_" }
Log "poll 12E3 + attach..."
$found=$false
for ($i=0; $i -lt 120; $i++) {
  $out = usbipd list 2>&1
  if ($out -match '12e3') {
    Log "12E3 SEEN iter $i"
    $found=$true
    # attach directly (persisted bind may exist)
    $a = usbipd attach --wsl Debian --busid 2-1 2>&1
    Log "attach: $a"
    if ($a -notmatch 'attached' -and $a -notmatch 'success') {
      Log "attach retry w/ bind..."
      usbipd bind --busid 2-1 --force 2>&1 | ForEach-Object { Log "bind: $_" }
      $a2 = usbipd attach --wsl Debian --busid 2-1 2>&1
      Log "attach2: $a2"
    }
    break
  }
  Start-Sleep -Milliseconds 50
}
if (-not $found) { Log "12E3 NOT seen"; Log "=== END ==="; exit 1 }
Log "running WSL probe..."
wsl -d Debian -u root -- python3 /mnt/c/Users/timpa/Desktop/steelseries_firmware_backup/usb_only_work/wsl_probe_v3.py 2>&1 | ForEach-Object { Log "wsl: $_" }
Log "=== END ==="
