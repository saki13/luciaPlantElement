# One-command quality gate.
# NOTE: ASCII-only on purpose -- Windows PowerShell 5.1 parses BOM-less UTF-8
#       .ps1 files as ANSI, which breaks on non-ASCII comments. It also turns a
#       native command's stderr into a terminating NativeCommandError when
#       $ErrorActionPreference = "Stop" is set, so we keep it at Continue and
#       check $LASTEXITCODE explicitly instead.
#
# Stages:
#   1. python unit tests      balance / engine / scenarios / replay / golden sync
#   2. sprite health          sheet structure, aspect outliers, multi-character frames
#   3. calibration baseline   20 runs/scene, exact match against the baseline
#   4. level regression       every data/levels/*.json actually simulated
#   5. render assertions      app_pygame loads 21 sheets, animates, renders non-flat
#   6. conformance gate       GDScript resolve_hit vs Python oracle (needs Godot)
#
# Usage:
#   pwsh -File scripts\check_all.ps1
#   pwsh -File scripts\check_all.ps1 -SkipGodot
#
# Env overrides: PVZ_PYTHON, PVZ_GODOT, PVZ_SHOT_DIR

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

function Run-Step([string]$title, [scriptblock]$body) {
    Write-Host ""
    Write-Host "== $title =="
    & $body 2>&1 | ForEach-Object { "$_" } | Write-Host
    $code = $LASTEXITCODE
    if ($code -ne 0) { $script:failed += $title }
}

Push-Location $root
$sw = [System.Diagnostics.Stopwatch]::StartNew()

Run-Step "1/6 python unit tests" {
    & $py -m unittest tests.test_balance tests.test_engine tests.test_scenarios `
        tests.test_replay tests.test_golden_sync tests.test_session
}

Run-Step "2/6 sprite health check" {
    & $py scripts\check_sprites.py
}

Run-Step "3/6 calibration baseline" {
    & $py scripts\check_calibration.py
}

Run-Step "4/6 level regression" {
    & $py scripts\check_levels.py
}

Run-Step "5/6 render assertions" {
    $dir = $env:PVZ_SHOT_DIR
    if (-not $dir) { $dir = Join-Path $root "logs" }
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    & $py scripts\check_render.py --shot-dir $dir
}

if ($SkipGodot) {
    Write-Host ""
    Write-Host "== 6/6 conformance gate == SKIPPED (-SkipGodot)"
} else {
    Run-Step "6/6 resolve_hit conformance gate" {
        & (Join-Path $PSScriptRoot "run_conformance.ps1")
    }
}

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
