@echo off
title KIU: verify the recompiled library
rem Runs every recompiled function against the interpreter; see
rem Verify-Library.ps1. Output: build\diagnostics\verify-library.txt
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify-Library.ps1"
