@echo off
title KIU: build the runtime, then play
rem Rebuilds tools\zakuro (zakuro-pc-interface.exe) and starts the game with
rem Launch-KIU.cmd. The build log is build\runtime-build.log.
cd /d "%~dp0"
taskkill /im zakuro-pc-interface.exe >nul 2>&1
timeout /t 2 >nul
echo Building the runtime, a few minutes...
powershell -NoProfile -ExecutionPolicy Bypass -File tools\recomp\Build-Runtime.ps1 > build\runtime-build.log 2>&1
if errorlevel 1 (echo BUILD FAILED, see build\runtime-build.log & pause & exit /b 1)
echo BUILD OK >> build\runtime-build.log
start "" "%~dp0Launch-KIU.cmd"
