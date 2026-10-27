@echo off
rem Render capture session for the chapter 9 white screen: when the screen
rem stays white, press F8 and keep playing for a second (doc/DIAGNOSTICS.md).
call "%~dp0Launch-KIU.cmd" --render-capture %*
