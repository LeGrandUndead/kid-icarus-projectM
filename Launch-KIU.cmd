@echo off
cd /d "%~dp0"
python "%~dp0tools\recomp\launch.py" %*
if errorlevel 1 pause
