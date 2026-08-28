<#
.SYNOPSIS
    Makes WSL boot silently at Windows login, without needing Task
    Scheduler permissions -- drops a tiny hidden-window launcher into your
    own Startup folder instead. Combined with `loginctl enable-linger`
    (which install_linux_systemd.sh does automatically), this is the
    missing piece for surviving a full reboot: linger makes systemd start
    the collector service as soon as the WSL VM boots, but Windows never
    boots WSL on its own after a restart -- something has to ask it to.
    This is that something.

.NOTES
    Run this from a normal, NON-admin Windows PowerShell window (not
    inside WSL/bash). Deliberately avoids Register-ScheduledTask -- that
    requires Task Scheduler permissions some machines/accounts don't have
    ("Access is denied"). Writing one file to your own Startup folder
    needs no special permissions at all.

.EXAMPLE
    .\scripts\windows\register_wsl_autostart.ps1
.EXAMPLE
    .\scripts\windows\register_wsl_autostart.ps1 -DistroName Ubuntu
#>

param(
    [string]$DistroName = ""   # leave blank to use your default WSL distro
)

$ErrorActionPreference = "Stop"

$startupDir = [Environment]::GetFolderPath("Startup")
$vbsPath = Join-Path $startupDir "optionsurface-wsl-autostart.vbs"

# `true` is a no-op that exists on every Linux distro -- we don't need it to
# do anything, just to make wsl.exe boot the VM (which starts systemd/PID 1,
# which then starts any lingering user's services, including the collector).
if ($DistroName -ne "") {
    $wslCommand = "wsl.exe -d $DistroName -e true"
} else {
    $wslCommand = "wsl.exe -e true"
}

# A .vbs wrapper is the standard trick for a fully hidden (WindowStyle 0)
# launch at login -- a .bat or shortcut pointed straight at wsl.exe tends to
# flash a console window briefly; WScript.Shell.Run doesn't.
$vbsContent = @"
' Boots WSL silently at login so the optionsurface collector (systemd
' --user, linger-enabled) comes back up after a reboot -- see
' scripts/unix/install_linux_systemd.sh for the Linux side of this.
Set objShell = CreateObject("WScript.Shell")
objShell.Run "$wslCommand", 0, False
"@

Set-Content -Path $vbsPath -Value $vbsContent -Encoding ASCII

Write-Host "Installed: $vbsPath"
Write-Host "WSL will now boot silently the next time you log in to Windows."
Write-Host "No admin rights needed for this -- it only writes to your own Startup folder."
Write-Host ""
Write-Host "Test it right now instead of waiting to log out/in:"
Write-Host "    wscript.exe `"$vbsPath`""
Write-Host "Then, inside a WSL terminal, confirm the collector is running:"
Write-Host "    systemctl --user status optionsurface-collector.service"
Write-Host ""
Write-Host "This only works if linger is enabled for your Linux user (the WSL"
Write-Host "installer does this automatically now). If you're not sure, run inside WSL:"
Write-Host "    loginctl show-user `$USER --property=Linger"
Write-Host "It should say 'Linger=yes'. If it says 'no': sudo loginctl enable-linger `$USER"
Write-Host ""
Write-Host "Remove this later by deleting the file:"
Write-Host "    Remove-Item `"$vbsPath`""