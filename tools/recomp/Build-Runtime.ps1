# Rebuilds the playable runtime, tools/zakuro/target/release/
# zakuro-pc-interface.exe (what Launch-KIU.cmd starts), from tools/zakuro.
# The executable it replaces is kept once in archive/<date>-runtime-before/.
# Saves and settings are not touched.
param([string]$Archive = '')

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/environment.ps1"
$ErrorActionPreference = 'Continue'
$exe = Join-Path $kiuRoot 'tools/zakuro/target/release/zakuro-pc-interface.exe'
if (-not $Archive) { $Archive = Join-Path $kiuRoot ("archive/{0}-runtime-before" -f (Get-Date -Format 'yyyy-MM-dd')) }
if ((Test-Path -LiteralPath $exe) -and -not (Test-Path -LiteralPath (Join-Path $Archive 'zakuro-pc-interface.exe'))) {
    New-Item -ItemType Directory -Force $Archive | Out-Null
    Copy-Item -LiteralPath $exe $Archive
    Write-Host "Previous runtime kept in $Archive"
}
Push-Location (Join-Path $kiuRoot 'tools/zakuro')
cargo build --release --locked -p zakuro --bin zakuro-pc-interface
$built = $LASTEXITCODE
Pop-Location
if ($built) { throw "Runtime build failed ($built)" }
Write-Host "Built $exe"
