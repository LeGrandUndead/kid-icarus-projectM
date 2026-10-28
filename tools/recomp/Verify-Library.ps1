# Checks the recompiled game library against the interpreter: 3dsrecomp's
# verify runs each recompiled function both ways from the same made-up state
# and reports every one whose registers, flags, VFP state or memory differ.
# A mismatch is a translation bug (or an interpreter one) to look at.
# Output: build/diagnostics/verify-library.txt. Read-only on the library,
# the ROM and the saves.
param([int]$Count = 1000000)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/environment.ps1"
$ErrorActionPreference = 'Continue'
$out = Join-Path $kiuRoot 'build/diagnostics/verify-library.txt'
New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null
$rom = Join-Path $kiuRoot 'Kid Icarus - Uprising (USA) (En,Fr,Es).3ds'
$library = Join-Path $kiuRoot 'build/kiu-aot-o2/0004000000030100.dll'
Push-Location (Join-Path $kiuRoot 'tools/3dsrecomp')
"building 3dsrecomp with verify, $(Get-Date)" | Set-Content $out
cargo build --release --features verify 2>&1 | Add-Content $out
if ($LASTEXITCODE) { "BUILD FAILED" | Add-Content $out; Pop-Location; exit 1 }
"verifying $library ($Count functions at most), $(Get-Date)" | Add-Content $out
& ./target/release/3dsrecomp.exe verify $rom $library $Count 2>&1 | Add-Content $out
"done $(Get-Date), exit $LASTEXITCODE" | Add-Content $out
Pop-Location
