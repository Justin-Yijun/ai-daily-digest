# AI Daily Digest - local fallback runner
# ---------------------------------------------------------------------------
# Why: GitHub Actions cron is unreliable (missed both slots on 2026-10-06), so the
# local machine is the primary trigger and GitHub is the backup. This script is
# idempotent, so it is safe to run it several times a day:
#
#   1. pull from GitHub  -> if today's digest is already there, GitHub won, stop
#   2. otherwise collect + build weekly + build site locally
#   3. commit + push (only if something changed)
#
# Registered as Windows task "ai-daily-digest" (daily 16:45, repeats every 60 min
# for 4h). Its status shows up on http://172.17.150.20/scheduler-status.html
# automatically via the existing task-status-report job.
#
# GitHub SSH port 22 is blocked from this machine, so all git traffic goes through
# ssh.github.com:443 instead. If the proxy/VPN is off the pull/push will fail and
# the task reports a non-zero exit code - turn the proxy on and the next repeat of
# the task will pick it up.
#
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 parses BOM-less UTF-8 as
# GBK, so any non-ASCII literal here would be corrupted.

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root 'logs'
$Log = Join-Path $LogDir 'local_run.log'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# git over ssh.github.com:443 (port 22 is blocked here)
$Remote = 'ssh://git@ssh.github.com:443/Justin-Yijun/ai-daily-digest.git'
$GitKey = Join-Path $env:USERPROFILE '.ssh\id_ed25519_github'
$env:GIT_SSH_COMMAND = "ssh -i `"$GitKey`" -o IdentitiesOnly=yes -o StrictHostKeyChecking=no -o ConnectTimeout=25"
$Python = Join-Path $env:USERPROFILE 'AppData\Local\Python\bin\python.exe'
if (-not (Test-Path $Python)) { $Python = 'python' }

function Log($msg) {
    $line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Add-Content -LiteralPath $Log -Value $line -Encoding UTF8
    Write-Host $line
}

$Today = Get-Date -Format 'yyyy-MM-dd'
Set-Location $Root
Log ('=== start  date={0}  root={1}' -f $Today, $Root)

# ---------------------------------------------------------------- 1) pull
$Pulled = $false
$out = & git pull --rebase --autostash $Remote main 2>&1
$out | ForEach-Object { Log ('  pull: ' + $_) }
if ($LASTEXITCODE -eq 0) { $Pulled = $true } else { Log 'WARN: git pull failed (proxy/VPN off?)' }

# No network -> we can neither verify nor push. Fail loudly so the status page
# shows a non-zero result and the next repeat (or the user) can retry.
if (-not $Pulled) {
    Log 'FAIL: cannot reach GitHub (proxy/VPN off?) - turn it on and the next repeat will retry'
    exit 1
}

# --------------------------------------------------- 2) did GitHub already do it?
# Ask the remote tree directly: if it already carries today's digest, GitHub won.
# (Do NOT just check the local file: a previous run may have built it locally
#  but failed to push, and then we still need to push it.)
$Digest = Join-Path $Root ('digest\' + $Today + '.json')
if ($Pulled) {
    & git cat-file -e ('FETCH_HEAD:digest/' + $Today + '.json') 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Log 'OK: digest already published by GitHub Actions - nothing to do'
        exit 0
    }
}
# --------------------------------------------------- 3) collect locally
if (Test-Path $Digest) {
    Log 'digest already built locally (previous push likely failed) - skip collection'
} else {
    if (-not $env:NVIDIA_API_KEY) {
        $cfg = Join-Path $env:USERPROFILE '.pi\agent\models.json'
        if (Test-Path $cfg) {
            try {
                $j = Get-Content -LiteralPath $cfg -Raw -Encoding UTF8 | ConvertFrom-Json
                $k = $j.providers.'nvidia-nim'.apiKey
                if ($k) { $env:NVIDIA_API_KEY = $k; Log 'NVIDIA_API_KEY loaded from models.json' }
            } catch { Log ('WARN: cannot read models.json: ' + $_) }
        }
    }
    if (-not $env:NVIDIA_API_KEY) { Log 'WARN: no NVIDIA_API_KEY - summaries will be skipped' }

    foreach ($step in @('collect.py', 'build_weekly.py', 'build_site.py')) {
        $sp = Join-Path $Root ('scripts\' + $step)
        Log ('run ' + $step)
        & $Python $sp 2>&1 | ForEach-Object { Log ('  ' + $_) }
        if ($LASTEXITCODE -ne 0) {
            Log ('FAIL: ' + $step + ' exit ' + $LASTEXITCODE)
            exit 1
        }
    }
}

# --------------------------------------------------- 4) commit + push
& git add digest weekly state site README.md 2>&1 | Out-Null
& git diff --cached --quiet 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Log 'OK: nothing to commit'
    exit 0
}
& git -c user.name='local-runner' -c user.email='local@localhost' commit -m ('chore(digest): ' + $Today + ' AI digest (local fallback)') 2>&1 | ForEach-Object { Log ('  ' + $_) }
$out = & git push $Remote main 2>&1
$out | ForEach-Object { Log ('  push: ' + $_) }
if ($LASTEXITCODE -ne 0) {
    Log 'FAIL: git push failed (proxy/VPN off?) - next repeat will retry'
    exit 1
}
Log 'OK: done'
exit 0
