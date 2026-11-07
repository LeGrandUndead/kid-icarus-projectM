@echo off
title KIU: deleting the project leftovers
rem Deletes the leftovers agreed on November 7 2026 (tools\recomp\Clean-Up.ps1).
rem Permanent. Keeps the game, saves and settings, ROM, toolchains, source
rem and git history. Log: build\cleanup.log.
cd /d "%~dp0"
echo Deleting the leftovers, a few minutes...
powershell -NoProfile -ExecutionPolicy Bypass -File tools\recomp\Clean-Up.ps1 > build\cleanup.log 2>&1
type build\cleanup.log
pause
