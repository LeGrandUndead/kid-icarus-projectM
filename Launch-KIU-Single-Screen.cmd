@echo off
cd /d "%~dp0"
python "%~dp0tools\recomp\launch.py" --single-screen --display 1080p --texture-filter original %*
if errorlevel 1 pause
