$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$audit = Join-Path $root 'build/ai-hd-edition/asset-audit'
$assembly = [Reflection.Assembly]::LoadFrom((Join-Path $root 'tools/SPICA/SPICA.dll'))
$decode = $assembly.GetType('SPICA.PICA.Converters.TextureConverter').GetMethod('DecodeBuffer')
$manifest = Get-Content -LiteralPath (Join-Path $audit 'containers.json') -Raw | ConvertFrom-Json
$decoded = Join-Path $audit 'decoded'
New-Item -ItemType Directory -Force $decoded | Out-Null
$rows = [Collections.Generic.List[object]]::new()
$failures = [Collections.Generic.List[object]]::new()
$seen = @{}
$index = 0
foreach ($container in $manifest) {
    try {
        $gfx = [SPICA.Formats.CtrGfx.Gfx]::Open($container.path)
        foreach ($texture in $gfx.Textures) {
            if ($texture.GetType().Name -ne 'GfxTextureImage') { continue }
            $w = $texture.Width; $h = $texture.Height
            if ($w -lt 8 -or $h -lt 8 -or $w * $h -gt 262144) { continue }
            $raw = $texture.Image.RawBuffer
            $sha = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($raw))
            $key = "$w-$h-$($texture.HwFormat)-$sha"
            $origin = [PSCustomObject]@{ containers=$container.sources; texture=$texture.Name }
            if ($seen.ContainsKey($key)) { $seen[$key].origins.Add($origin); continue }
            $rgba = $decode.Invoke($null,@($raw,[int]$w,[int]$h,$texture.HwFormat))
            $file = "$($rows.Count).rgba"
            [IO.File]::WriteAllBytes((Join-Path $decoded $file),$rgba)
            $origins = [Collections.Generic.List[object]]::new();$origins.Add($origin)
            $row=[PSCustomObject]@{ file=$file; width=$w; height=$h; format=[string]$texture.HwFormat; origins=$origins }
            $rows.Add($row);$seen[$key]=$row
        }
    } catch { $failures.Add([PSCustomObject]@{path=$container.path; error=$_.Exception.Message}) }
    $index++
    if ($index % 100 -eq 0) { Write-Output "$index / $($manifest.Count) containers; $($rows.Count) unique textures" }
}
$rows | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $audit 'decoded.json')
$failures | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $audit 'decode-failures.json')
Write-Output "Decoded $($rows.Count) unique textures; $($failures.Count) failed containers"
