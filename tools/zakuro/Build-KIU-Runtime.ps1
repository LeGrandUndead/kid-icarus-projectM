$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$kiuRoot = [IO.Path]::GetFullPath((Join-Path $scriptDir '.'))
# If this script is copied into tools\zakuro, project root is two levels up.
if (Test-Path (Join-Path $kiuRoot 'Cargo.toml')) {
    $zakuroRoot = $kiuRoot
    $kiuRoot = [IO.Path]::GetFullPath((Join-Path $zakuroRoot '../..'))
} else {
    throw 'Put Build-KIU-Runtime.ps1 in D:\Games\Kid icarus\tools\zakuro'
}

$envScript = Join-Path $kiuRoot 'tools/recomp/environment.ps1'
if (-not (Test-Path $envScript)) { throw "Missing $envScript" }
. $envScript

Push-Location $zakuroRoot
try {
    Write-Host 'Building KIU runtime fork (release)...'
    cargo build --release --locked -p zakuro
    if ($LASTEXITCODE) { throw "cargo build failed with exit code $LASTEXITCODE" }

    $exe = Join-Path $zakuroRoot 'target/release/zakuro.exe'
    if (-not (Test-Path $exe)) { throw "Build succeeded but $exe is missing" }
    Write-Host ''
    Write-Host 'Runtime build complete:'
    Get-Item $exe | Select-Object FullName,Length,LastWriteTime
    Write-Host ''
    Write-Host 'PC controls: WASD runs, Alt walks, Shift generates a deliberate dash flick, F2 captures mouse, left mouse = L/attack.'
} finally {
    Pop-Location
}
