# One-command quality gate.
# NOTE: ASCII-only on purpose -- Windows PowerShell 5.1 parses BOM-less UTF-8
#       .ps1 files as ANSI, which breaks on non-ASCII comments. It also turns a
#       native command's stderr into a terminating NativeCommandError when
#       $ErrorActionPreference = "Stop" is set, so we keep it at Continue and
#       check $LASTEXITCODE explicitly instead.
#
# Runs, in order:
#   1. python unit tests            (balance / engine / scenarios / replay / golden sync)
#   2. sprite health check          (aspect outliers + multi-character source frames)
#   3. resolve_hit conformance gate (GDScript vs Python oracle, needs Godot)
#   4. pygame smoke                 (render shell stays runnable)
#
# Usage:
#   pwsh -File scripts\check_all.ps1
#   pwsh -File scripts\check_all.ps1 -SkipGodot
#
# Env overrides: PVZ_PYTHON, PVZ_GODOT

param(
    [switch]$SkipGodot
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$failed = @()

if ($env:PVZ_PYTHON) {
    $py = $env:PVZ_PYTHON
} else {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $cmd) { Write-Host "python not found; set PVZ_PYTHON"; exit 2 }
    $py = $cmd.Source
}

Push-Location $root
$sw = [System.Diagnostics.Stopwatch]::StartNew()

Write-Host "== 1/4 python unit tests =="
& $py -m unittest tests.test_balance tests.test_engine tests.test_scenarios `
    tests.test_replay tests.test_golden_sync 2>&1 | ForEach-Object { "$_" } | Write-Host
if ($LASTEXITCODE -ne 0) { $failed += "unit tests" }

Write-Host ""
Write-Host "== 2/4 sprite health check =="
& $py scripts\check_sprites.py 2>&1 | ForEach-Object { "$_" } | Write-Host
if ($LASTEXITCODE -ne 0) { $failed += "sprite health" }

Write-Host ""
if ($SkipGodot) {
    Write-Host "== 3/4 conformance gate == SKIPPED (-SkipGodot)"
} else {
    Write-Host "== 3/4 resolve_hit conformance gate =="
    & (Join-Path $PSScriptRoot "run_conformance.ps1") 2>&1 | ForEach-Object { "$_" } | Write-Host
    if ($LASTEXITCODE -ne 0) { $failed += "conformance gate" }
}

Write-Host ""
Write-Host "== 4/4 pygame smoke =="
$env:SDL_VIDEODRIVER = "dummy"
$env:SDL_AUDIODRIVER = "dummy"
$env:PYTHONPATH = (Join-Path $root "libs") + ";" + $root
if ($env:PVZ_SMOKE_SHOT) {
    $shot = $env:PVZ_SMOKE_SHOT
} else {
    $logDir = Join-Path $root "logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
    $shot = Join-Path $logDir "check_all_app.png"
}
& $py -m tdgame.app_pygame --smoke --frames 2 --shot $shot 2>&1 | ForEach-Object { "$_" } | Write-Host
if ($LASTEXITCODE -ne 0) { $failed += "pygame smoke" }

Pop-Location
$sw.Stop()

Write-Host ""
Write-Host ("=" * 56)
if ($failed.Count -gt 0) {
    Write-Host ("CHECK_ALL: FAIL  ({0})" -f ($failed -join ", "))
    exit 1
}
Write-Host ("CHECK_ALL: PASS  ({0}s)" -f [math]::Round($sw.Elapsed.TotalSeconds, 1))
exit 0
