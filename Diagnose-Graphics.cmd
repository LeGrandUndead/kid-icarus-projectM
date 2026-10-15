@echo off
cd /d "%~dp0"
echo Go to the scene with the pattern, press F8 once, then play for a few seconds and quit normally.
call Launch-KIU.cmd --resolution 1 --render-capture --record-input --input-trace %*
