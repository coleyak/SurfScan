<#
.SYNOPSIS
    Registers run_collector.py as a Windows Scheduled Task so it keeps
    collecting option-chain snapshots without a terminal window open --
    starts automatically when you log in, runs hidden, restarts itself if
    it ever crashes, and logs to a file instead of a console.

.NOTES
    Does NOT run if the computer is fully powered off or asleep -- it needs
    Windows to be running and you logged in (the screen can be locked).
    If you want collection that survives your laptop being off entirely,
    that needs a remote/cloud server instead -- ask if you want that next.

.EXAMPLE
    .\scripts\windows\register_scheduled_task.ps1 -Tickers AAPL,MSFT,SPY -IntervalMinutes 15

.EXAMPLE
    # If PowerShell blocks the script from running (default on many machines):
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\scripts\windows\register_scheduled_task.ps1 -Tickers AAPL,MSFT,SPY
#>

param(
    [Parameter(Mandatory = $true)]
    [string[]]$Tickers,

    [int]$IntervalMinutes = 15,
    [int]$MaxExpiries = 6,
    [string]$ProjectDir = (Resolve-Path "$PSScriptRoot\..\..").Path,
    [string]$PythonExe = "python.exe",
    [string]$TaskName = "OptionSurfaceCollector"
)

$ErrorActionPreference = "Stop"

$logDir = Join-Path $ProjectDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "collector.log"

$scriptPath = Join-Path $ProjectDir "scripts\run_collector.py"
if (-not (Test-Path $scriptPath)) {
    throw "Couldn't find run_collector.py at $scriptPath -- run this from the project, or pass -ProjectDir explicitly."
}

$tickerArgs = $Tickers -join " "

# Routed through cmd.exe so stdout/stderr can be redirected to a log file --
# with no terminal window open, `print()` output has nowhere else to go.
# `-u` disables Python's output buffering, which kicks in automatically
# when stdout isn't a real terminal -- without it, the log file would only
# update in delayed chunks instead of as things actually happen.
$argumentList = "/c cd /d `"$ProjectDir`" && `"$PythonExe`" -u `"$scriptPath`" $tickerArgs " +
                "--interval $IntervalMinutes --max-expiries $MaxExpiries >> `"$logFile`" 2>&1"

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument $argumentList -WorkingDirectory $ProjectDir
$trigger = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet `
    -Hidden `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)   # zero = no time limit (default would kill it after 72h)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "optionsurface: collects option-chain snapshots for $tickerArgs every $IntervalMinutes min, market hours only" `
    -Force | Out-Null

Write-Host "Registered scheduled task '$TaskName'."
Write-Host "It starts automatically next time you log in. To start it right now instead of waiting:"
Write-Host "    Start-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "Check on it:"
Write-Host "    Get-ScheduledTaskInfo -TaskName '$TaskName'          # last run time, result code"
Write-Host "    Get-Content '$logFile' -Tail 20 -Wait                # follow the log live"
Write-Host ""
Write-Host "Stop / remove it later:"
Write-Host "    Stop-ScheduledTask -TaskName '$TaskName'"
Write-Host "    Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
