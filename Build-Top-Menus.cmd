@echo off
title KIU: top-screen menus build
cd /d "%~dp0"
taskkill /im zakuro-pc-interface.exe >nul 2>&1
timeout /t 2 >nul
echo Building the runtime, a few minutes...
powershell -NoProfile -ExecutionPolicy Bypass -File tools\recomp\Build-Runtime.ps1 > build\top-menus-build.log 2>&1
if errorlevel 1 (echo BUILD FAILED, see build\top-menus-build.log & pause & exit /b 1)
echo BUILD OK >> build\top-menus-build.log
start "" "%~dp0Launch-KIU.cmd"
