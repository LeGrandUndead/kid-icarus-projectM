@echo off
title KIU: relaunch
cd /d "%~dp0"
taskkill /im zakuro-pc-interface.exe >nul 2>&1
timeout /t 2 >nul
start "" "%~dp0Launch-KIU.cmd" --menu-capture
