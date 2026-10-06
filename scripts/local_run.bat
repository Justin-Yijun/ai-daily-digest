@echo off
rem AI Daily Digest - local fallback runner (cmd wrapper for Task Scheduler)
rem Registered as Windows task "ai-daily-digest". Keep this file ASCII-only.
setlocal
set PDIR=%~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%PDIR%local_run.ps1"
exit /b %ERRORLEVEL%
