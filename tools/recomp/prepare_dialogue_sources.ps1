# Original, local ROM bytes only. No image generation or texture replacement.
$ErrorActionPreference = 'Stop'
$uiRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$uiOut = Join-Path $uiRoot 'build/native-ui/dialogue-sources'
New-Item -ItemType Directory -Force $uiOut | Out-Null
$uiAssembly = [Reflection.Assembly]::LoadFrom((Join-Path $uiRoot 'tools/SPICA/SPICA.dll'))
$uiRows = [Collections.Generic.List[object]]::new()
foreach ($uiFile in Get-ChildItem -LiteralPath (Join-Path $uiRoot 'ROM/gameFiles/RomFS/us/info') -Recurse -Filter '*.bcres') {
    $uiGfx = [SPICA.Formats.CtrGfx.Gfx]::Open($uiFile.FullName)
    foreach ($uiTex in $uiGfx.Textures) {
        if ($uiTex.Name -notmatch '^FB_[0-9]+$' -or $uiTex.GetType().Name -ne 'GfxTextureImage') { continue }
        $uiName = "$($uiRows.Count).bin"
        [IO.File]::WriteAllBytes((Join-Path $uiOut $uiName), $uiTex.Image.RawBuffer)
        $uiRows.Add([PSCustomObject]@{ file=$uiName; name=$uiTex.Name; width=$uiTex.Width; height=$uiTex.Height; format=[string]$uiTex.HwFormat; source=$uiFile.FullName })
    }
}
ConvertTo-Json -InputObject @($uiRows.ToArray()) -Depth 5 | Set-Content -LiteralPath (Join-Path $uiOut 'sources.json')
& python (Join-Path $PSScriptRoot 'prepare_dialogue_sources.py')
if ($LASTEXITCODE -ne 0) { throw 'Dialogue source fingerprinting failed' }
