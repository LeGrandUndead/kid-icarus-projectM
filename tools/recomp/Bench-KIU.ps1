# Headless, repeatable benchmark of the runtime: the same save, the same
# recorded input, the same number of vertical blanks, rendered on the GPU at
# 5x like the PC build. Writes the usage report (host time per frame, renderer
# phases, GPU work, swaps) into build\bench\<name>-<time>\ and copies it to
# build\bench\latest-usage.txt.
#
#   Bench-KIU.ps1                      the original 30 fps cadence
#   Bench-KIU.ps1 -Fps60               the 60 fps scheduler from vblank 6000
#   Bench-KIU.ps1 -Frames 16500        longer, reaches land gameplay
#   Bench-KIU.ps1 -KeepAliased         the renderer's old write-back path, for comparison
#
# Screens are saved in the run folder at vblanks 6000, 7500 and the last one
# (-DumpAt '6000,6150,...' for others). -Resolution sets the internal scale.
#
# Needs the recording from the 60 fps research (build\60fps-research\baseline)
# and the archived initial save. Saves and the playable build are not touched.
param([int]$Frames = 9000, [switch]$Fps60, [string]$Name = '', [switch]$NoBuild, [switch]$KeepAliased, [int]$Resolution = 5, [string]$DumpAt = '')

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/environment.ps1"
$ErrorActionPreference = 'Continue'
$baseline = Join-Path $kiuRoot 'build/60fps-research/baseline'
$save = Join-Path $kiuRoot 'archive/2026-10-16-cleanup/build/input-traces/20261009-072852-462179/initial-save/user'
foreach ($needed in @((Join-Path $baseline 'input.replay'), (Join-Path $baseline 'sysdata'), $save)) {
    if (-not (Test-Path -LiteralPath $needed)) { throw "Missing $needed" }
}
$target = Join-Path $kiuRoot 'build/bench-target'
if (-not $NoBuild) {
    Push-Location (Join-Path $kiuRoot 'tools/zakuro')
    cargo build --release --locked -p zakuro-core --example boot --target-dir $target
    $built = $LASTEXITCODE
    Pop-Location
    if ($built) { throw "Benchmark build failed ($built)" }
}
$exe = Join-Path $target 'release/examples/boot.exe'

if (-not $Name) { $Name = $(if ($Fps60) { 'fps60' } else { 'fps30' }) }
$run = Join-Path $kiuRoot ("build/bench/{0}-{1}" -f $Name, (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force $run | Out-Null
Copy-Item -LiteralPath $save -Destination $run -Recurse
Copy-Item -LiteralPath (Join-Path $baseline 'sysdata') -Destination $run -Recurse
Copy-Item -LiteralPath (Join-Path $kiuRoot 'build/kiu-aot-o2/0004000000030100.dll') -Destination $run
$env:APPDATA = Join-Path $run 'roaming'
$env:LOCALAPPDATA = Join-Path $run 'local'
New-Item -ItemType Directory -Force $env:APPDATA, $env:LOCALAPPDATA | Out-Null
# the pipeline cache the playable build made, so shader compiles do not
# dominate the run
$cache = Join-Path $kiuRoot 'build/user-data/gameplay-preview/local/zakuro/pipelines.bin'
if (Test-Path -LiteralPath $cache) {
    New-Item -ItemType Directory -Force (Join-Path $env:LOCALAPPDATA 'zakuro') | Out-Null
    Copy-Item -LiteralPath $cache (Join-Path $env:LOCALAPPDATA 'zakuro/pipelines.bin')
}
$env:ZAKURO_RECOMPILED = Join-Path $run '0004000000030100.dll'
$env:ZAKURO_REPLAY = Join-Path $baseline 'input.replay'
$env:ZAKURO_RASTERIZER = 'hardware'
$env:ZAKURO_RESOLUTION = "$Resolution"
$env:ZAKURO_PRESENT = 'direct'
if (-not $DumpAt) { $DumpAt = "6000,7500,$Frames" }
$env:ZAKURO_DUMP_AT = $DumpAt
# the screen dumps go to the temporary folder: make that the run folder
$env:TMP = $run
$env:TEMP = $run
if ($KeepAliased) { $env:ZAKURO_KEEP_ALIASED = '1' } else { Remove-Item Env:ZAKURO_KEEP_ALIASED -ErrorAction SilentlyContinue }
$env:RUST_LOG = 'warn'
if ($Fps60) {
    $env:KIU_TEST_FRAME_INTERVAL = '1'
    $env:KIU_TEST_FRAME_INTERVAL_FROM = '6000'
    $env:KIU_TEST_RESET_CARRY = '1'
    $env:KIU_TEST_HALF_STEP = '1'
} else {
    Remove-Item Env:KIU_TEST_FRAME_INTERVAL -ErrorAction SilentlyContinue
}
$rom = Get-ChildItem -LiteralPath $kiuRoot -Filter '*.3ds' -File | Select-Object -First 1
$started = Get-Date
Push-Location $run
& $exe $rom.FullName $Frames 1> (Join-Path $run 'runtime.stdout.log') 2> (Join-Path $run 'runtime.stderr.log')
$code = $LASTEXITCODE
Pop-Location
$seconds = ((Get-Date) - $started).TotalSeconds
Remove-Item -LiteralPath (Join-Path $run '0004000000030100.dll') -ErrorAction SilentlyContinue
$usage = Join-Path $run '0004000000030100.usage.txt'
"# bench $Name, $Frames vblanks, exit $code, $([math]::Round($seconds,1)) s wall" | Set-Content (Join-Path $kiuRoot 'build/bench/latest-usage.txt')
if (Test-Path -LiteralPath $usage) { Get-Content $usage | Add-Content (Join-Path $kiuRoot 'build/bench/latest-usage.txt') }
Write-Host "Done: $run ($([math]::Round($seconds,1)) s, exit $code)"
