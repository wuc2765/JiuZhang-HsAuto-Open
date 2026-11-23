param(
    [string]$CleanRoot = '',
    [string]$OutDir = '',
    [string]$Manifest = '',
    [string]$Official = '',
    [string]$AssetsDir = '',
    [string]$BaselineAssets = '',
    [string]$InstallersDir = '',
    [string]$Python = '',
    [string]$Hsbundle = '',
    [switch]$Audit,
    [switch]$SkipBuild,
    [switch]$UseOfficialRepack
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
function Step($n,$t){ Write-Host ("`n== [" + $n + "] " + $t) -ForegroundColor Cyan }
function Die($m){ Write-Host ("[x] " + $m) -ForegroundColor Red; exit 1 }

if (-not $CleanRoot) { $CleanRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
if (-not $OutDir) { $OutDir = Join-Path $CleanRoot 'out\release' }
if (-not $Manifest) { $Manifest = Join-Path $CleanRoot 'release-manifest.json' }
if (-not $AssetsDir) { $AssetsDir = Join-Path $CleanRoot 'assets' }
if (-not $BaselineAssets) {
    $BaselineAssets = $env:HSAUTO_BASELINE_ASSETS
    if (-not $BaselineAssets) { $BaselineAssets = Join-Path $CleanRoot 'build-inputs\baseline-assets' }
}
if (-not $InstallersDir) {
    $InstallersDir = $env:HSAUTO_INSTALLERS_DIR
    if (-not $InstallersDir) { $InstallersDir = Join-Path $AssetsDir '环境安装包' }
}
if (-not $Python) {
    $Python = $env:HSAUTO_PYTHON
    if (-not $Python) { $Python = 'python' }
}
if (-not $Hsbundle) { $Hsbundle = Join-Path $CleanRoot 'tools\hsbundle.py' }
if (-not $Official) { $Official = $env:HSAUTO_OFFICIAL_PACKAGE }
if (-not $Official) {
    Die '缺少官方 0.9.75 运行包：请设置 HSAUTO_OFFICIAL_PACKAGE 或传入 -Official <解包目录>'
}

$CoreProj = Join-Path $CleanRoot 'core-src\HsAuto.Core.csproj'
$UiProj = Join-Path $CleanRoot 'src\HsAuto.csproj'
$PluginProj = Join-Path $CleanRoot 'plugin-src\hdt.csproj'
$CoreDll = Join-Path $CleanRoot 'core-src\bin\Release\net8.0\HsAuto.Core.dll'
$UiDll = Join-Path $CleanRoot 'src\bin\Release\net8.0-windows7.0\HsAuto.dll'
$PluginDll = Join-Path $CleanRoot 'plugin-src\bin\Release\netstandard2.0\hdt.dll'

if (-not $SkipBuild) {
    Step 1 'Build Core'
    & dotnet build $CoreProj -c Release --nologo -v q | Out-Null
    if ($LASTEXITCODE -ne 0) { Die 'Core build failed' }
    Step 2 'Build UI'
    & dotnet build $UiProj -c Release --nologo -v q | Out-Null
    if ($LASTEXITCODE -ne 0) { Die 'UI build failed' }
    Step 3 'Build plugin'
    & dotnet build $PluginProj -c Release --nologo -v q | Out-Null
    if ($LASTEXITCODE -ne 0) { Die 'plugin build failed' }
}
foreach ($p in @($CoreDll,$UiDll,$PluginDll)) { if (-not (Test-Path $p)) { Die "missing build output: $p" } }

Step 4 'Clean output directory'
if (Test-Path $OutDir) { Remove-Item $OutDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$manifestObj = Get-Content $Manifest -Raw -Encoding UTF8 | ConvertFrom-Json
function Copy-Target([string]$src, [string]$rel) {
    $dst = Join-Path $OutDir $rel
    $parent = Split-Path $dst -Parent
    if ($parent -and -not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    Copy-Item $src $dst -Force
}

Step 5 'Assemble whitelist'
$generated = @{}
foreach ($entry in $manifestObj.files) {
    $rel = [string]$entry.path
    switch ([string]$entry.action) {
        'remove' { continue }
        'keep' {
            switch ([string]$entry.origin) {
                'generated' {
                    switch ($rel) {
                        'HsAuto.dll' { Copy-Target $UiDll $rel; $generated[$rel] = $true }
                        'hdt.dll'    { Copy-Target $PluginDll $rel; $generated[$rel] = $true }
                        'HsAuto.exe' { continue }
                        default { Die "unknown generated path: $rel" }
                    }
                }
                'official-runtime' {
                    $src = Join-Path $Official $rel
                    if (-not (Test-Path $src)) { Die "official runtime missing: $src" }
                    Copy-Target $src $rel
                }
                'own' {
                    $src = Join-Path $BaselineAssets $rel
                    if (-not (Test-Path $src)) { $src = Join-Path $AssetsDir $rel }
                    if ($rel -eq 'WebView2Loader.dll') { $src = Join-Path $CleanRoot 'refs\bundle975\WebView2Loader.dll' }
                    if (-not (Test-Path $src) -and $rel -like '环境安装包/*') { $src = Join-Path $InstallersDir (Split-Path $rel -Leaf) }
                    if (-not (Test-Path $src)) { Die "own asset missing: $rel (expected under $AssetsDir or baseline)" }
                    Copy-Target $src $rel
                }
                default { Die "unknown origin for keep: $rel / $($entry.origin)" }
            }
        }
        'replace' {
            $src = Join-Path $AssetsDir $rel
            if (-not (Test-Path $src)) {
                $src = Join-Path $BaselineAssets $rel
                if (Test-Path $src) {
                    Write-Host ("   [audit] baseline asset used: " + $rel) -ForegroundColor Yellow
                } else {
                    Die "replace asset missing: $rel"
                }
            }
            Copy-Target $src $rel
        }
        default { Die "unknown action: $($entry.action) / $rel" }
    }
}

Step 6 'Build HsAuto.exe (D6 self-built single-file; optional official repack)'
$stage = Join-Path $CleanRoot 'out\_stage'
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null
$UiRidDll = Join-Path $CleanRoot 'src\bin\Release\net8.0-windows7.0\win-x64\HsAuto.dll'
$stageUiDll = if (Test-Path $UiRidDll) { $UiRidDll } else { $UiDll }
$officialExe = Join-Path $Official 'HsAuto.exe'
$bundleExe = $null
if ($UseOfficialRepack) {
    Copy-Item $UiDll   (Join-Path $stage 'HsAuto.dll') -Force
    Copy-Item $CoreDll (Join-Path $stage 'HsAuto.Core.dll') -Force
    $outExe = Join-Path $CleanRoot 'out\_HsAuto.exe'
    & $Python -I $Hsbundle repack $officialExe $stage $outExe 'HsAuto.dll' 'HsAuto.Core.dll'
    if ($LASTEXITCODE -ne 0) { Die 'repack failed' }
    Copy-Target $outExe 'HsAuto.exe'
} else {
    $publishDir = Join-Path $CleanRoot 'out\_publish'
    if (Test-Path $publishDir) { Remove-Item $publishDir -Recurse -Force }
    & dotnet publish $UiProj -c Release -r win-x64 --self-contained true `
        -p:PublishSingleFile=true -p:EnableCompressionInSingleFile=true `
        -p:IncludeNativeLibrariesForSelfExtract=true -p:DebugType=None `
        -p:DebugSymbols=false -p:StaticWebAssetsEnabled=false `
        --nologo -v q -clp:ErrorsOnly -o $publishDir | Out-Null
    if ($LASTEXITCODE -ne 0) { Die 'single-file publish failed' }
    $publishedExe = Join-Path $publishDir 'HsAuto.exe'
    if (-not (Test-Path $publishedExe)) { Die "published exe missing: $publishedExe" }
    Copy-Target $publishedExe 'HsAuto.exe'
    if (Test-Path $UiRidDll) { Copy-Target $UiRidDll 'HsAuto.dll' }
    Copy-Item $stageUiDll (Join-Path $stage 'HsAuto.dll') -Force
    Copy-Item $CoreDll   (Join-Path $stage 'HsAuto.Core.dll') -Force
    $bundleExe = Join-Path $CleanRoot 'out\_verify_HsAuto.exe'
    & $Python -I $Hsbundle repack $officialExe $stage $bundleExe 'HsAuto.dll' 'HsAuto.Core.dll'
    if ($LASTEXITCODE -ne 0) { Die 'verification repack failed' }
}

Step 7 'Verify'
$extract = Join-Path $CleanRoot 'out\_verify_release'
$verifyArgs = @('-I', (Join-Path $CleanRoot 'tools\verify_release.py'),
    '--release', $OutDir, '--manifest', $Manifest, '--official', $Official,
    '--python', $Python, '--hsbundle', $Hsbundle, '--extract-dir', $extract)
if ($bundleExe) { $verifyArgs += @('--bundle-exe', $bundleExe) }
if ($Audit) { $verifyArgs += '--audit' }
& $Python @verifyArgs
$code = $LASTEXITCODE
Write-Host ""
Write-Host ("[OUT] " + $OutDir) -ForegroundColor Green
if ($code -ne 0) { Write-Host "[!] verification failed (expected in Phase 0; assets still baseline)" -ForegroundColor Yellow }
exit $code
