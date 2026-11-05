# Build a standalone Windows exe with PyInstaller.
#
# Why a venv: the Anaconda environment ships an obsolete `pathlib` backport
# which makes PyInstaller refuse to run, and the Anaconda dir is read-only.
# A clean venv (without system site-packages) sidesteps both problems.
#
# Usage:  pwsh -File tools\build_exe.ps1
#
# Output: dist\PVZLike.exe   (onefile, ~25 MB)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$venv = Join-Path $root "_work\venv"
$vpy = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $vpy)) {
    Write-Host "== creating clean venv =="
    $sys = $env:PVZ_PYTHON
    if (-not $sys) { $sys = "D:\ProgramData\anaconda3\python.exe" }
    if (-not (Test-Path $sys)) { $sys = "python" }
    & $sys -m venv $venv
    & $vpy -m pip install --quiet --no-cache-dir pyinstaller pygame numpy pillow
}

Write-Host "== building exe =="
& $vpy -m PyInstaller --noconfirm --onefile --console `
    --name "PVZLike" `
    --paths "$root" --paths "$root\libs" `
    --add-data "$root\tdgame\data;tdgame/data" `
    --add-data "$root\anim_demo\animation.py;anim_demo" `
    --add-data "$root\anim_demo\assets\sprites;anim_demo/assets/sprites" `
    --distpath "$root\dist" --workpath "$root\_work\pyi" --specpath "$root\_work" `
    "$root\_work\entry_game.py"

Write-Host ""
Get-ChildItem (Join-Path $root "dist\*.exe") |
    ForEach-Object { Write-Host ("output: {0}  {1} MB" -f $_.Name, [math]::Round($_.Length / 1MB, 1)) }
