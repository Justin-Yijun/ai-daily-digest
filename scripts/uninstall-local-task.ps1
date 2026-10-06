# Remove the Windows scheduled task "ai-daily-digest".
# Usage: powershell -ExecutionPolicy Bypass -File scripts\uninstall-local-task.ps1

$ErrorActionPreference = 'Stop'
$TaskName = 'ai-daily-digest'

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "removed: $TaskName"
} else {
    Write-Host "not found: $TaskName (nothing to do)"
}
