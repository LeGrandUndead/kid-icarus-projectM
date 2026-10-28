@echo off
title KIU: build, then a render capture session
rem When something draws wrong, press F8 in that scene and keep playing a
rem second: two frames are written draw by draw to build\texture-traces\<time>
rem (doc/DIAGNOSTICS.md, Render capture).
cd /d "%~dp0"
taskkill /im zakuro-pc-interface.exe >nul 2>&1
timeout /t 2 >nul
echo Building the runtime, a few minutes...
powershell -NoProfile -ExecutionPolicy Bypass -File tools\recomp\Build-Runtime.ps1 > build\runtime-build.log 2>&1
if errorlevel 1 (echo BUILD FAILED, see build\runtime-build.log & pause & exit /b 1)
echo BUILD OK >> build\runtime-build.log
start "" "%~dp0Launch-KIU.cmd" --render-capture
