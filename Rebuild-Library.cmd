@echo off
title KIU: build the runtime, then rebuild the game library (about 2 hours)
rem Builds tools\zakuro (log build\runtime-build.log), then regenerates and
rem recompiles the game library with the hints and the overrides in
rem tools\recomp\overrides (tools\recomp\Rebuild-KIU-With-Hints.ps1, log
rem build\rebuild-hints.log). The old library is kept as
rem build\kiu-aot-o2-previous. Does not start the game: Launch-KIU.cmd does.
cd /d "%~dp0"
taskkill /im zakuro-pc-interface.exe >nul 2>&1
timeout /t 2 >nul
echo Building the runtime, a few minutes...
powershell -NoProfile -ExecutionPolicy Bypass -File tools\recomp\Build-Runtime.ps1 > build\runtime-build.log 2>&1
if errorlevel 1 (echo RUNTIME BUILD FAILED, see build\runtime-build.log & pause & exit /b 1)
echo BUILD OK >> build\runtime-build.log
echo Rebuilding the game library, about two hours. Log: build\rebuild-hints.log
powershell -NoProfile -ExecutionPolicy Bypass -File tools\recomp\Rebuild-KIU-With-Hints.ps1 > build\rebuild-hints.log 2>&1
if errorlevel 1 (echo LIBRARY REBUILD FAILED, see build\rebuild-hints.log & pause & exit /b 1)
echo LIBRARY OK >> build\rebuild-hints.log
echo Done. Start Launch-KIU.cmd to play.
pause
