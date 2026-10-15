@echo off
cd /d "%~dp0"
python "%~dp0tools\recomp\launch.py" --display 1080p %*
if errorlevel 1 pause
