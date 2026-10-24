# Build the Windows app folder and a distributable zip. Uses a separate
# build environment (.build-venv), so the development venv is not modified.
# Works in Windows PowerShell 5.1 and PowerShell 7.
#
# Environment overrides:
#   PYTHON       Python used to create the build environment
#                (default: "py -3.12" if the launcher exists, else "python")
#   APP_VERSION  Version embedded in the zip name (default 0.0.0-dev.<commit>)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

if (-not $env:APP_VERSION) {
    $env:APP_VERSION = "0.0.0-dev.$(git rev-parse --short HEAD)"
}
$BuildVenv = '.build-venv'
$VenvPython = Join-Path $BuildVenv 'Scripts\python.exe'
$AppDir = 'dist\LU2MET_NR'
$Zip = "dist\LU2MET_NR-windows-x64-$($env:APP_VERSION).zip"

Write-Host "==> Building LU2MET NR Filter $($env:APP_VERSION) for Windows"

if (-not (Test-Path $VenvPython)) {
    Write-Host '==> Creating build environment'
    if ($env:PYTHON) {
        Invoke-Checked $env:PYTHON @('-m', 'venv', $BuildVenv)
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        Invoke-Checked 'py' @('-3.12', '-m', 'venv', $BuildVenv)
    } else {
        Invoke-Checked 'python' @('-m', 'venv', $BuildVenv)
    }
}
Invoke-Checked $VenvPython @('-m', 'pip', 'install', '--quiet', '--upgrade', 'pip')
Invoke-Checked $VenvPython @('-m', 'pip', 'install', '--quiet', '-r', 'requirements-build.txt')

Write-Host '==> Building novasdr_nr Rust extension'
foreach ($dir in 'build', 'dist') {
    if (Test-Path $dir) { Remove-Item -Recurse -Force $dir }
}
Invoke-Checked (Join-Path $BuildVenv 'Scripts\maturin.exe') @(
    'build', '--release', '--locked', '-m', '..\novasdr_nr_py\Cargo.toml', '-o', 'build\wheels'
)
$Wheel = (Get-ChildItem 'build\wheels\*.whl' | Select-Object -First 1).FullName
Invoke-Checked $VenvPython @('-m', 'pip', 'install', '--quiet', '--force-reinstall', '--no-deps', $Wheel)

Write-Host '==> Running tests'
Invoke-Checked $VenvPython @('-m', 'unittest', 'discover', '-s', 'tests', '-p', 'tests_*.py')

Write-Host '==> Packaging with PyInstaller'
Invoke-Checked $VenvPython @('-m', 'PyInstaller', '--noconfirm', '--clean', 'LU2MET_NR.spec')

Write-Host '==> Self-test of the packaged app'
# The app is a GUI executable, so wait for it explicitly to get its exit code.
$env:QT_QPA_PLATFORM = 'offscreen'
$SelfTest = Start-Process -FilePath "$AppDir\LU2MET_NR.exe" -ArgumentList '--self-test' -Wait -PassThru -NoNewWindow
Remove-Item Env:QT_QPA_PLATFORM
if ($SelfTest.ExitCode -ne 0) {
    $Log = Join-Path $HOME 'novasdr_debug.log'
    if (Test-Path $Log) { Get-Content $Log -Tail 40 }
    throw "Packaged app self-test failed with exit code $($SelfTest.ExitCode)"
}

Write-Host "==> Creating $Zip"
Compress-Archive -Path $AppDir -DestinationPath $Zip -Force

Write-Host ''
Write-Host 'Build complete:'
Write-Host "  App: audio_processor\$AppDir\LU2MET_NR.exe"
Write-Host "  Zip: audio_processor\$Zip"
