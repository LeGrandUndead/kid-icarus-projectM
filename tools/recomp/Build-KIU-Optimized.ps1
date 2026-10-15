param(
    [int]$Jobs = 6,
    [ValidateSet('1','2')][string]$Optimization = '2',
    [string]$Source = ''
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/environment.ps1"

if ($Jobs -lt 1) { throw 'Jobs must be positive' }

# Codex previously found that 16 parallel GCC jobs exhausted 16 GB of RAM,
# while six completed successfully. Six is therefore the default.
if ($Source) {
    $sourceDir = [IO.Path]::GetFullPath($Source)
} else {
    $candidates = Get-ChildItem -LiteralPath (Join-Path $kiuRoot 'build') `
        -Recurse -Filter 'entries.c' -File -ErrorAction SilentlyContinue |
        ForEach-Object {
            $dir = $_.Directory
            $header = Join-Path $dir.FullName 'recomp.h'
            if (Test-Path -LiteralPath $header) {
                $count = @(Get-ChildItem -LiteralPath $dir.FullName -Filter '*.c' -File).Count
                [PSCustomObject]@{
                    Path = $dir.FullName
                    Count = $count
                    Modified = $_.LastWriteTime
                }
            }
        } |
        Where-Object { $_.Count -ge 100 } |
        Sort-Object Modified -Descending

    if (-not $candidates) {
        throw @'
Could not find the generated 3dsrecomp C directory automatically.
Pass it explicitly:
  .\Build-KIU-Optimized.ps1 -Source "D:\path\to\generated-c"
The directory must contain entries.c, recomp.h and the generated .c files.
'@
    }

    $sourceDir = $candidates[0].Path
}

Write-Host "Generated C source: $sourceDir"

$outDir = Join-Path $kiuRoot "build/kiu-aot-o$Optimization"
New-Item -ItemType Directory -Force $outDir | Out-Null

Write-Host "Output:             $outDir"
Write-Host "Compiler workers:   $Jobs"
Write-Host "Optimization:       -O$Optimization"
Write-Host ''
Write-Host 'The build is incremental. If it is interrupted, rerun the same command.'

& python "$kiuRoot/tools/recomp/compile_generated.py" `
    $sourceDir `
    $outDir `
    --compiler $env:CC `
    --jobs $Jobs `
    --optimization $Optimization

if ($LASTEXITCODE) {
    throw "Optimized AOT build failed with exit code $LASTEXITCODE"
}

$library = Join-Path $outDir '0004000000030100.dll'
$result = Join-Path $outDir 'build-result.json'
if (-not (Test-Path -LiteralPath $library) -or -not (Test-Path -LiteralPath $result)) {
    throw 'Build finished without the expected DLL/build-result.json'
}

Write-Host ''
Write-Host 'Optimized AOT build completed.'
Get-Item -LiteralPath $library | Select-Object FullName,Length,LastWriteTime
Write-Host ''
Write-Host 'Quick native smoke test (300 headless frames)...'

& python "$kiuRoot/tools/recomp/launch.py" --build o2 --headless 300
if ($LASTEXITCODE) {
    throw "Headless smoke test failed with exit code $LASTEXITCODE"
}

Write-Host ''
Write-Host 'PASS: O2 build completed and survived the 300-frame native smoke test.'
Write-Host 'Launch normally with Launch-KIU.cmd; updated launch.py will prefer this O2 build.'
