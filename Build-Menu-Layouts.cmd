@echo off
title KIU: menu layouts build and capture
cd /d "%~dp0"
taskkill /im zakuro-pc-interface.exe >nul 2>&1
timeout /t 2 >nul
echo Cataloguing the menu art from your ROM...
python tools\recomp\prepare_native_ui_sources.py > build\menu-layouts-build.log 2>&1
if errorlevel 1 (echo CATALOG FAILED, see build\menu-layouts-build.log & pause & exit /b 1)
echo Building the runtime, a few minutes...
powershell -NoProfile -ExecutionPolicy Bypass -File tools\recomp\Build-Runtime.ps1 >> build\menu-layouts-build.log 2>&1
if errorlevel 1 (echo BUILD FAILED, see build\menu-layouts-build.log & pause & exit /b 1)
echo BUILD OK >> build\menu-layouts-build.log
start "" "%~dp0Launch-KIU.cmd" --ui-census --menu-capture
