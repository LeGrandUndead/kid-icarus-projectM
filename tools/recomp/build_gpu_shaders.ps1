# Rebuild only the shaders changed by the projected-texture correction.
$ErrorActionPreference = 'Stop'
$kiuRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$kiuCompiler = Join-Path $kiuRoot 'tools/toolchains/glslang-16.6.0/bin/glslang.exe'
$kiuShaderDir = Join-Path $kiuRoot 'tools/zakuro/crates/zakuro-gpu/shaders'
if (-not (Test-Path -LiteralPath $kiuCompiler)) {
    throw 'Missing project-local glslang 16.6.0. See doc/RENDERING_STATUS.md.'
}
foreach ($kiuSource in @('raster.vert', 'shade.vert', 'raster.frag')) {
    & $kiuCompiler -V (Join-Path $kiuShaderDir $kiuSource) -o (Join-Path $kiuShaderDir "$kiuSource.spv")
    if ($LASTEXITCODE) { throw "Shader compilation failed: $kiuSource" }
}
& $kiuCompiler -V -DWRITES_DEPTH (Join-Path $kiuShaderDir 'raster.frag') -o (Join-Path $kiuShaderDir 'raster_depth.frag.spv')
if ($LASTEXITCODE) { throw 'Depth shader compilation failed' }
