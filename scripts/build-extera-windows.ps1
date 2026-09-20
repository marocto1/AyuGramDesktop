param([switch]$CheckToolchain)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $repo
New-Item -ItemType Directory -Force build-logs | Out-Null

$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$installations = & $vswhere -latest -version '[17.0,19.0)' -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -format json | ConvertFrom-Json
if (-not $installations) { throw 'Visual Studio 2022 or 2026 with C++ x64 tools is required.' }
$vs = $installations[0].installationPath
$major = ([version]$installations[0].installationVersion).Major
$generator = if ($major -ge 18) { 'Visual Studio 18 2026' } else { 'Visual Studio 17 2022' }
Write-Output "Using $generator at $vs"
$vcvars = Join-Path $vs 'VC\Auxiliary\Build\vcvars64.bat'
$environment = & $env:ComSpec /d /c "call `"$vcvars`" -vcvars_ver=14.44 >nul && set"
if ($LASTEXITCODE -ne 0) { throw 'MSVC 14.44 environment setup failed.' }
foreach ($line in $environment) {
    if ($line -match '^([^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
    }
}
if ($CheckToolchain) {
    if ($env:VCToolsVersion -notlike '14.44.*' -or $env:Platform -ne 'x64') {
        throw 'Unexpected compiler version or architecture.'
    }
    Write-Output "TOOLCHAIN OK: MSVC $env:VCToolsVersion / $env:Platform"
    exit 0
}
$env:QT = '5.15.19'
$env:CMAKE_BUILD_PARALLEL_LEVEL = '2'
& python Telegram/build/prepare/prepare.py skip-release 2>&1 | Tee-Object build-logs/prepare.log
if ($LASTEXITCODE -ne 0) { throw 'Preparing upstream dependencies failed; see prepare.log.' }

$options = @('-S', '.', '-B', 'out', '-G', $generator, '-A', 'x64', '-T', 'v143',
    '-DCMAKE_SYSTEM_VERSION=10.0.26100.0', '-DDESKTOP_APP_DISABLE_AUTOUPDATE=ON',
    '-DDESKTOP_APP_DISABLE_CRASH_REPORTS=ON', '-DDESKTOP_APP_ENABLE_LTO=OFF',
    '-DCMAKE_CXX_FLAGS=/FS', '-DCMAKE_C_FLAGS=/FS')
if ($env:TDESKTOP_API_ID -and $env:TDESKTOP_API_HASH) {
    $options += "-DTDESKTOP_API_ID=$env:TDESKTOP_API_ID"
    $options += "-DTDESKTOP_API_HASH=$env:TDESKTOP_API_HASH"
    'Custom Telegram API credentials were used.' | Set-Content build-logs/api-mode.txt
} else {
    $options += '-DTDESKTOP_API_TEST=ON'
    'TEST API credentials: this artifact is for development, not public deployment. Set TDESKTOP_API_ID and TDESKTOP_API_HASH repository secrets for your own application.' | Set-Content build-logs/api-mode.txt
}
& cmake @options 2>&1 | Tee-Object build-logs/configure.log
if ($LASTEXITCODE -ne 0) { throw 'CMake configuration failed.' }
& cmake --build out --config Debug --target Telegram --parallel 2 2>&1 | Tee-Object build-logs/build.log
if ($LASTEXITCODE -ne 0) { throw 'Compiling Telegram failed.' }
if (-not (Test-Path -LiteralPath out/Debug/AyuGram.exe)) { throw 'Expected AyuGram.exe was not produced.' }
