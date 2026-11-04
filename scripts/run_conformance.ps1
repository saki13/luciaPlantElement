# Conformance gate (stage 2, step 1):
#   regenerate the golden cases from the Python oracle, then verify the GDScript
#   implementation against them with Godot headless.
#
# NOTE: this file is intentionally ASCII-only. Windows PowerShell 5.1 parses
# BOM-less UTF-8 .ps1 files as ANSI, which breaks on non-ASCII comments.
#
# Usage:
#   pwsh -File scripts\run_conformance.ps1
#
# Env overrides:
#   PVZ_PYTHON   python interpreter      (default: python on PATH)
#   PVZ_GODOT    Godot 4 executable      (default: auto-detect, then godot on PATH)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Resolve-Python {
    if ($env:PVZ_PYTHON) { return $env:PVZ_PYTHON }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "python not found; set PVZ_PYTHON"
}

function Resolve-Godot {
    if ($env:PVZ_GODOT) { return $env:PVZ_GODOT }
    $dirs = @("D:\apps\Godot", "C:\Program Files\Godot", "$env:LOCALAPPDATA\Programs\Godot")
    foreach ($dir in $dirs) {
        if (Test-Path $dir) {
            $hit = Get-ChildItem $dir -Filter "Godot_v*.exe" -ErrorAction SilentlyContinue |
                Sort-Object LastWriteTime -Descending | Select-Object -First 1
            if ($hit) { return $hit.FullName }
        }
    }
    $cmd = Get-Command godot -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "Godot not found; set PVZ_GODOT"
}

$py = Resolve-Python
$godot = Resolve-Godot

Write-Host "python : $py"
Write-Host "godot  : $godot"
Write-Host ""

Write-Host "== 1/2 generate golden cases =="
& $py (Join-Path $root "scripts\gen_golden_hits.py")
if ($LASTEXITCODE -ne 0) { throw "golden generation failed (exit $LASTEXITCODE)" }

Write-Host ""
Write-Host "== 2/2 Godot conformance check =="
& $godot --headless --path (Join-Path $root "godot") --script "res://tests/run_conformance.gd"
$code = $LASTEXITCODE

Write-Host ""
if ($code -eq 0) {
    Write-Host "CONFORMANCE: PASS"
} else {
    Write-Host "CONFORMANCE: FAIL (exit $code)"
}
exit $code
