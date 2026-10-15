# Dot-source this file to use only this project's portable build tools.
$kiuRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$env:CARGO_HOME = Join-Path $kiuRoot 'tools/toolchains/cargo'
$env:RUSTUP_HOME = Join-Path $kiuRoot 'tools/toolchains/rustup'
$kiuCompiler = Join-Path $kiuRoot 'tools/toolchains/winlibs/mingw64/bin'
$env:PATH = "$kiuCompiler;$env:CARGO_HOME/bin;$env:PATH"
$env:CC = Join-Path $kiuCompiler 'gcc.exe'
$env:CXX = Join-Path $kiuCompiler 'g++.exe'
$env:AR = Join-Path $kiuCompiler 'ar.exe'
$env:CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER = $env:CC
$env:CARGO_BUILD_JOBS = '2'
# Keep runtime saves, config, traces and recomp caches inside this project.
$env:APPDATA = Join-Path $kiuRoot 'build/user-data/roaming'
$env:LOCALAPPDATA = Join-Path $kiuRoot 'build/user-data/local'
New-Item -ItemType Directory -Force $env:APPDATA,$env:LOCALAPPDATA | Out-Null
