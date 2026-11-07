# Measures the project's folders, largest first within each level, and the
# free space on its drive. Reads only: nothing is changed or deleted.
# Folders over 1 GB are opened one level further (up to four levels).
# Disk-Report.cmd writes the result to build\disk-report.txt.
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

function Get-Size([string]$path) {
    $sum = (Get-ChildItem -LiteralPath $path -Recurse -Force -File -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum).Sum
    if ($sum) { [int64]$sum } else { [int64]0 }
}

function Show-Level([string]$path, [string]$name, [int]$depth) {
    $items = Get-ChildItem -LiteralPath $path -Force -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.PSIsContainer) { [pscustomobject]@{ Item = $_; Size = Get-Size $_.FullName } }
        else { [pscustomobject]@{ Item = $_; Size = [int64]$_.Length } }
    } | Sort-Object Size -Descending
    foreach ($entry in $items) {
        if ($entry.Size -lt 50MB) { continue }
        $label = if ($name) { "$name\$($entry.Item.Name)" } else { $entry.Item.Name }
        $kind = if ($entry.Item.PSIsContainer) { '\' } else { '' }
        '{0}{1,8:N2} GB  {2}{3}' -f ('    ' * $depth), ($entry.Size / 1GB), $label, $kind
        if ($entry.Item.PSIsContainer -and ($depth -lt 1 -or $entry.Size -ge 1GB) -and $depth -lt 3) {
            Show-Level $entry.Item.FullName $label ($depth + 1)
        }
    }
}

$total = Get-Size $root
"Project: $root"
'Total:   {0:N2} GB' -f ($total / 1GB)
$drive = Get-PSDrive -Name ((Split-Path -Qualifier $root).TrimEnd(':'))
'Free on {0}: {1:N2} GB' -f $drive.Name, ($drive.Free / 1GB)
'(items under 50 MB not shown)'
''
Show-Level $root '' 0
