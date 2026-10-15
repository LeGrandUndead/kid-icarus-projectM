param(
    [ValidateSet('interpreter', 'aot', 'own-startup')][string]$Mode = 'aot',
    [int]$Frames = 60,
    [switch]$MenuInput,
    [switch]$Hardware
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/environment.ps1"
if ($Frames -lt 1) { throw 'Frames must be positive' }
$kiuStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$kiuRun = Join-Path $kiuRoot "build/evaluation/$Mode-$Frames-$kiuStamp"
New-Item -ItemType Directory -Force $kiuRun | Out-Null
$env:TEMP = $kiuRun
$env:TMP = $kiuRun
$env:ZAKURO_CLOCK = '4000000000000'
$env:ZAKURO_DUMP_AT = "60,$Frames"
Remove-Item Env:ZAKURO_RECOMPILED,Env:ZAKURO_MASH_BUTTONS,Env:ZAKURO_RASTERIZER -ErrorAction SilentlyContinue
if ($MenuInput) { $env:ZAKURO_MASH_BUTTONS = '1' }
if ($Hardware) { $env:ZAKURO_RASTERIZER = 'hardware' }
if ($Mode -eq 'aot') {
    $env:ZAKURO_RECOMPILED = Join-Path $kiuRoot 'build/kiu-aot-debug/0004000000030100.dll'
} elseif ($Mode -eq 'own-startup') {
    $env:ZAKURO_RECOMPILED = Join-Path $kiuRoot 'build/own-startup/kiu.dll'
}
if ($Mode -ne 'interpreter' -and -not (Test-Path -LiteralPath $env:ZAKURO_RECOMPILED)) {
    throw 'Recompiled library has not been built'
}
$kiuLog = Join-Path $kiuRun 'run.log'
Push-Location $kiuRun
try {
    & "$kiuRoot/tools/zakuro/target/release/examples/boot.exe" "$kiuRoot/Kid Icarus - Uprising (USA) (En,Fr,Es).3ds" $Frames *> $kiuLog
    $kiuExit = $LASTEXITCODE
} finally {
    Pop-Location
}
Get-Content -LiteralPath $kiuLog -Tail 30
Write-Output "Full report and screen captures: $kiuRun"
if ($kiuExit -ne 0) { exit $kiuExit }
if (-not (Select-String -LiteralPath $kiuLog -SimpleMatch "outcome:       Completed after $Frames frames" -Quiet)) {
    throw 'Runtime did not complete the requested frame count; inspect the report'
}
