@echo off
cd /d "%~dp0"
echo Records which original lower-screen pictures and HUD pieces are drawn, to build\native-ui\census.
python "%~dp0tools\recomp\launch.py" --pc-interface --ui-census --display 1080p --texture-filter original %*
if errorlevel 1 pause
