# Recompiles the game with the places the runtime still had to interpret.
#
# Zakuro writes those places next to the library (0004000000030100.hints) as
# the game is played. 3dsrecomp takes them in as extra function starts, so
# the next library covers that code too. This script:
#   1. hands the hints to 3dsrecomp (it reads them from %APPDATA%\3dsrecomp),
#   2. regenerates the C into build\kiu-aot-next (generation only: CC points
#      at a program that refuses to compile, because 3dsrecomp's own compile
#      starts one gcc per core, which runs out of memory on this game),
#   3. compiles it with compile_generated.py into build\kiu-aot-o2-next,
#   4. swaps it in as build\kiu-aot-o2 (the old one becomes
#      build\kiu-aot-o2-previous) and runs a 300-frame headless smoke test,
#      swapping back if the test fails.
# Everything is logged to build\rebuild-hints.log. Takes about two hours.
param([int]$Jobs = 6)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/environment.ps1"
# native programs log to stderr; under 'Stop' Windows PowerShell would turn
# that into an error, so failures are checked by hand from here on.
$ErrorActionPreference = 'Continue'
$id = '0004000000030100'
$build = Join-Path $kiuRoot 'build'
$current = Join-Path $build 'kiu-aot-o2'
$generated = Join-Path $build 'kiu-aot-next'
$next = Join-Path $build 'kiu-aot-o2-next'
$previous = Join-Path $build 'kiu-aot-o2-previous'
$recomp = Join-Path $kiuRoot 'tools/3dsrecomp/target/release/3dsrecomp.exe'
$rom = Get-ChildItem -LiteralPath $kiuRoot -Filter '*.3ds' -File | Select-Object -First 1
if (-not $rom) { throw 'No .3ds in the project folder' }
if (-not (Test-Path -LiteralPath $recomp)) { throw "3dsrecomp is not built: $recomp" }

# 1. hints
$hints = Join-Path $current "$id.hints"
if (-not (Test-Path -LiteralPath $hints)) { throw "No hints yet: $hints (play a while first)" }
$hintDir = Join-Path $env:APPDATA '3dsrecomp'
New-Item -ItemType Directory -Force $hintDir | Out-Null
Copy-Item -LiteralPath $hints (Join-Path $hintDir "$id.hints") -Force -ErrorAction Stop
Write-Host "Hints: $((Get-Content -LiteralPath $hints | Where-Object { $_ -and -not $_.StartsWith('#') }).Count) addresses"

# 2. generate C only
if (-not (Test-Path -LiteralPath (Join-Path $generated 'entries.c'))) {
    New-Item -ItemType Directory -Force $generated | Out-Null
    $savedCC = $env:CC
    # python answers --version but refuses gcc's flags, so 3dsrecomp stops
    # right after writing the C.
    $env:CC = (Get-Command python).Source
    Write-Host 'Generating C with 3dsrecomp (its compile step is expected to fail)...'
    & $recomp build $rom.FullName $generated
    $env:CC = $savedCC
    if (-not (Test-Path -LiteralPath (Join-Path $generated 'entries.c'))) { throw '3dsrecomp wrote no C' }
} else {
    Write-Host "Reusing generated C in $generated"
}

# 3. compile (incremental, resumable)
& python "$kiuRoot/tools/recomp/compile_generated.py" $generated $next --compiler $env:CC --jobs $Jobs --optimization 2
if ($LASTEXITCODE) { throw "Compile failed ($LASTEXITCODE)" }
Copy-Item -LiteralPath $hints (Join-Path $next "$id.hints") -Force

# 4. swap and smoke test
if (Test-Path -LiteralPath $previous) { throw "$previous exists already; move it away first" }
Rename-Item -LiteralPath $current $previous -ErrorAction Stop
Rename-Item -LiteralPath $next $current -ErrorAction Stop
& python "$kiuRoot/tools/recomp/launch.py" --pc-interface --build o2 --headless 300
if ($LASTEXITCODE) {
    Write-Host 'Smoke test FAILED, putting the previous library back.'
    Rename-Item -LiteralPath $current $next
    Rename-Item -LiteralPath $previous $current
    throw 'Smoke test failed'
}
Write-Host 'PASS: new library in build\kiu-aot-o2, the old one in build\kiu-aot-o2-previous.'
