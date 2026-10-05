# 注册 Windows 计划任务：每天 16:30 同步 AI 前沿日报到本地
# 用法（普通权限即可）：powershell -ExecutionPolicy Bypass -File scripts\install-task.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Sync = Join-Path $Root "scripts\sync.ps1"
$TaskName = "AI-Daily-Digest-Sync"

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Sync`""

# GitHub Actions 在 16:00 跑，可能延迟 5~30 分钟，所以本地 16:45 再拉
$trigger = New-ScheduledTaskTrigger -Daily -At "16:45"

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "每天拉取 GitHub 上的 AI 前沿日报并弹通知" `
    -Force | Out-Null

Write-Host "已注册计划任务：$TaskName（每天 16:45）"
Write-Host "手动跑一次：Start-ScheduledTask -TaskName $TaskName"
Write-Host "删除任务：  Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
