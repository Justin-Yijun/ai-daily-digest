# AI 前沿日报 · 本地同步
# 作用：把 GitHub 仓库里的最新日报拉到本地（订阅目录），并弹一个 Windows 通知。
# 用法：powershell -ExecutionPolicy Bypass -File scripts\sync.ps1

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "[sync] 目录: $Root"

# 1) 拉取最新日报
Write-Host "[sync] git pull ..."
$pull = git pull --rebase --autostash 2>&1
Write-Host $pull
if ($LASTEXITCODE -ne 0) {
    Write-Host "[sync] git pull 失败，可能是网络问题（GitHub 通常直连可用，若不行请开代理）。"
}

# 2) 找最新的一篇日报
$latest = Get-ChildItem -Path (Join-Path $Root "digest") -Filter "*.md" -ErrorAction SilentlyContinue |
          Sort-Object Name -Descending | Select-Object -First 1

if (-not $latest) {
    Write-Host "[sync] 没找到日报文件。"
    exit 1
}

# 3) 生成一个「最新.md」方便直接打开
Copy-Item $latest.FullName (Join-Path $Root "最新.md") -Force
Write-Host "[sync] 最新日报: $($latest.Name)"

# 4) 统计摘要行，用于通知
$lines = Get-Content $latest.FullName -Encoding UTF8
$head = ($lines | Where-Object { $_ -match "^> 生成时间" } | Select-Object -First 1)
$picks = ($lines | Where-Object { $_ -match "^### \d+\." } | Measure-Object).Count
$msg = "$($latest.BaseName) 已更新，精选 $picks 条。`n$head"

# 5) 弹通知（多级回退，失败也不影响主流程）
$ok = $false
try {
    Import-Module BurntToast -ErrorAction Stop
    New-BurntToastNotification -Text "AI 前沿日报" -Body $msg
    $ok = $true
} catch { }

if (-not $ok) {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $ni = New-Object System.Windows.Forms.NotifyIcon
        $ni.Icon = [System.Drawing.SystemIcons]::Information
        $ni.Visible = $true
        $ni.ShowBalloonTip(10000, "AI 前沿日报", $msg, [System.Windows.Forms.ToolTipIcon]::Info)
        Start-Sleep -Seconds 6
        $ni.Dispose()
        $ok = $true
    } catch { }
}

if (-not $ok) {
    Write-Host "[sync] $msg"
}

# 6) 需要的话自动打开（取消下面注释）
# Start-Process $latest.FullName
