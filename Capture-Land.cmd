@echo off
cd /d "%~dp0"
echo This keeps your saved rendering resolution and records a test session.
echo Go to the blurry land area, press F8 once, play for a few seconds, then quit normally.
echo Recording can cause stutters; use Launch-KIU for normal play.
call Launch-KIU.cmd --render-capture --record-input --input-trace --diagnostics %*
