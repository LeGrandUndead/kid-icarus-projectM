# Deletes the project's leftovers, as agreed on November 7 2026 (see
# Disk-Report.cmd for the sizes): old archives, research recordings and
# dumps, generated C, build caches, the library from before October 30, and
# git objects no branch or log refers to. Permanent: nothing goes to the
# Recycle Bin. Never touches build\user-data (saves and settings), the
# current game library (build\kiu-aot-o2), the runtime, the ROM, the
# toolchains, the source or the git history. Clean-Up.cmd logs to
# build\cleanup.log.
$ErrorActionPreference = 'Continue'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$keepRoot = Join-Path $root 'build\user-data'

function Get-Size([string]$path) {
    $sum = (Get-ChildItem -LiteralPath $path -Recurse -Force -File -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum).Sum
    if ($sum) { [int64]$sum } else { [int64]0 }
}

$script:freed = [int64]0
function Remove-Leftover([string]$relative) {
    $path = Join-Path $root $relative
    $full = [System.IO.Path]::GetFullPath($path)
    if (-not $full.StartsWith($root + '\', [System.StringComparison]::OrdinalIgnoreCase) -or
        $full.StartsWith($keepRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        "REFUSED  $relative (outside what may be deleted)"; return
    }
    if (-not (Test-Path -LiteralPath $full)) { "absent   $relative"; return }
    $item = Get-Item -LiteralPath $full -Force
    $size = if ($item.PSIsContainer) { Get-Size $full } else { [int64]$item.Length }
    Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $full) {
        $left = Get-Size $full
        '{0,8:N2} GB  PARTLY   {1} ({2:N2} GB could not be deleted, in use?)' -f (($size - $left) / 1GB), $relative, ($left / 1GB)
        $script:freed += $size - $left
    } else {
        '{0,8:N2} GB  deleted  {1}' -f ($size / 1GB), $relative
        $script:freed += $size
    }
}

$drive = Get-PSDrive -Name ((Split-Path -Qualifier $root).TrimEnd(':'))
"Clean-up of $root, $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
'Free on {0} before: {1:N2} GB' -f $drive.Name, ($drive.Free / 1GB)
''

# old copies: builds, runtimes, experiments (the code is in git)
Remove-Leftover 'archive'

# research recordings and dumps, except what the benchmark and the map use
Get-ChildItem -LiteralPath (Join-Path $root 'build\60fps-research') -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne 'baseline' } |
    ForEach-Object { Remove-Leftover "build\60fps-research\$($_.Name)" }
Get-ChildItem -LiteralPath (Join-Path $root 'build\bench') -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -ne 'fine30-20261021-050926' } |
    ForEach-Object { Remove-Leftover "build\bench\$($_.Name)" }
Remove-Leftover 'build\diagnostics\white-out'
Remove-Leftover 'build\texture-traces'

# rebuilt when needed
Remove-Leftover 'build\kiu-aot-next'
Remove-Leftover 'build\bench-target'
Remove-Leftover 'build\kiu-aot-o2-previous'
Remove-Leftover 'tools\toolchains\winlibs.zip'

# git: what the big object is, then drop the objects nothing refers to
''
$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) {
    # the folder belongs to another Windows account (an older install), so
    # git refuses it unless told it is safe, for these commands only: the
    # global git settings are left alone
    $safe = 'safe.directory=' + ($root -replace '\\', '/')
    $big = '52b9a1ff0484e503a40a4041392320ba929d5145'
    $kind = & git -c $safe -C $root cat-file -t $big 2>$null
    if ($kind) { "git object $big`: $kind, $([math]::Round([int64](& git -c $safe -C $root cat-file -s $big) / 1GB, 2)) GB" }
    & git -c $safe -C $root count-objects -vH 2>&1 | ForEach-Object { "git before: $_" }
    $before = Get-Size (Join-Path $root '.git')
    & git -c $safe -C $root gc --prune=now --quiet 2>&1 | ForEach-Object { "git: $_" }
    & git -c $safe -C $root count-objects -vH 2>&1 | ForEach-Object { "git after: $_" }
    $after = Get-Size (Join-Path $root '.git')
    '{0,8:N2} GB  freed    .git (git gc --prune=now: {1:N2} GB left)' -f (($before - $after) / 1GB), ($after / 1GB)
    $script:freed += $before - $after
} else {
    'git not found: .git left as it is'
}

''
$drive = Get-PSDrive -Name ((Split-Path -Qualifier $root).TrimEnd(':'))
'Freed:  {0:N2} GB' -f ($script:freed / 1GB)
'Free on {0} after: {1:N2} GB' -f $drive.Name, ($drive.Free / 1GB)
'Project now: {0:N2} GB' -f ((Get-Size $root) / 1GB)
