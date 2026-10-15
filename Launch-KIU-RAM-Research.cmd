@echo off
cd /d "%~dp0"
rem Research: F7 saves game memory to build\ram-snapshots\<time> (compare with tools\recomp\ram_diff.py)
python "%~dp0tools\recomp\launch.py" --pc-interface --display 1080p --texture-filter original --ram-snapshots %*
if errorlevel 1 pause
