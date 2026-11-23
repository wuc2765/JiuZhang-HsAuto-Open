param(
    [string]$Release = '',
    [string]$Manifest = '',
    [string]$Official = $env:HSAUTO_OFFICIAL_PACKAGE,
    [string]$Python = $env:HSAUTO_PYTHON,
    [string]$GameDir = '',
    [switch]$Audit
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if (-not $Release) { $Release = Join-Path $root 'out\release' }
if (-not $Manifest) { $Manifest = Join-Path $root 'release-manifest.json' }
if (-not $Python) { $Python = 'python' }
if (-not $Official) {
    Write-Error '缺少官方 0.9.75 运行包：请设置 HSAUTO_OFFICIAL_PACKAGE 或传入 -Official <解包目录>'
    exit 1
}
$argsList = @(
    '-I', (Join-Path $PSScriptRoot 'verify_release.py'),
    '--release', $Release,
    '--manifest', $Manifest,
    '--official', $Official,
    '--python', $Python,
    '--hsbundle', (Join-Path $PSScriptRoot 'hsbundle.py'),
    '--extract-dir', (Join-Path $root 'out\_verify_release')
)
if ($GameDir) { $argsList += @('--game-dir', $GameDir) }
if ($Audit) { $argsList += '--audit' }
& $Python @argsList
exit $LASTEXITCODE
