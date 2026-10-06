# Register the Windows scheduled task "ai-daily-digest".
# Daily at 16:45, repeating every 60 min for 4 h  ->  16:45 17:45 18:45 19:45 20:45.
# The runner is idempotent, so the extra attempts are harmless no-ops once the
# digest exists (whichever of GitHub Actions / this machine finishes first wins).
#
# Its status then shows up on http://172.17.150.20/scheduler-status.html through
# the existing "task-status-report" job (every 15 min).
#
# Usage: powershell -ExecutionPolicy Bypass -File scripts\install-local-task.ps1

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Bat = Join-Path $Root 'scripts\local_run.bat'
$Hidden = Join-Path $env:USERPROFILE '.pi\scripts\run_hidden.vbs'
$TaskName = 'ai-daily-digest'

if (-not (Test-Path $Bat)) { throw "runner not found: $Bat" }
if (-not (Test-Path $Hidden)) { throw "hidden launcher not found: $Hidden" }

$action = New-ScheduledTaskAction -Execute 'wscript.exe' `
    -Argument ('"{0}" cmd /c "{1}"' -f $Hidden, $Bat)

# daily trigger at 16:45 ...
$trigger = New-ScheduledTaskTrigger -Daily -At '16:45'
# ... plus a repetition: every 60 min for 4 h (16:45 -> 20:45)
$rep = (New-ScheduledTaskTrigger -Once -At '16:45' `
        -RepetitionInterval (New-TimeSpan -Hours 1) `
        -RepetitionDuration (New-TimeSpan -Hours 4)).Repetition
$trigger.Repetition = $rep

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings `
    -Description 'AI frontier daily digest: local fallback runner (idempotent, 16:45 + every 60 min x4)' `
    -Force | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName
$i = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Host ("registered: {0}  state={1}" -f $t.TaskName, $t.State)
Write-Host ("next run  : {0}" -f $i.NextRunTime)
Write-Host ''
Write-Host 'run once now : Start-ScheduledTask -TaskName ai-daily-digest'
Write-Host 'remove task  : powershell -ExecutionPolicy Bypass -File scripts\uninstall-local-task.ps1'
