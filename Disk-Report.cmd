@echo off
title KIU: measuring the project folder (reads only)
rem Writes the size of every big folder to build\disk-report.txt.
rem Nothing is changed or deleted.
cd /d "%~dp0"
echo Measuring the project folder, a minute or two...
powershell -NoProfile -ExecutionPolicy Bypass -File tools\recomp\Disk-Report.ps1 > build\disk-report.txt 2>&1
echo Done: build\disk-report.txt
timeout /t 5 >nul
