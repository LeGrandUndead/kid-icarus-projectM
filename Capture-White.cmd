@echo off
title KIU: build, then a render capture session
rem For the chapter 9 white screen: when the screen stays white, press F8
rem and keep playing a second; two frames are written draw by draw
rem (doc/DIAGNOSTICS.md, Render capture).
cd /d "%~dp0"
taskkill /im zakuro-pc-interface.exe >nul 2>&1
timeout /t 2 >nul
echo Building the runtime, a few minutes...
powershell -NoProfile -ExecutionPolicy Bypass -File tools\recomp\Build-Runtime.ps1 > build\capture-build.log 2>&1
if errorlevel 1 (echo BUILD FAILED, see build\capture-build.log & pause & exit /b 1)
echo BUILD OK >> build\capture-build.log
start "" "%~dp0Launch-KIU.cmd" --render-capture
