# MapFree — Windows Installer Script
# Run from an elevated PowerShell prompt:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\scripts\install_windows.ps1
#
# What this script does:
#   1. Checks for Python 3.10+
#   2. Creates a .venv virtual environment in the repo root
#   3. Installs all Python dependencies
#   4. Installs mapfree in editable mode (adds the `mapfree` CLI)
#   5. Verifies the installation

param (
    [string]$PythonExe = "python",
    [switch]$SkipVenv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvDir  = Join-Path $RepoRoot ".venv"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "    OK: $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    WARNING: $msg" -ForegroundColor Yellow }

# ---------------------------------------------------------------------------
# 1. Check Python version
# ---------------------------------------------------------------------------
Write-Step "Checking Python version..."
try {
    $ver = & $PythonExe -c "import sys; print('%d.%d' % sys.version_info[:2])"
    $parts = $ver -split '\.'
    if ([int]$parts[0] -lt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -lt 10)) {
        Write-Error "Python 3.10+ is required. Found: $ver"
        exit 1
    }
    Write-OK "Python $ver"
} catch {
    Write-Error "Python not found. Install Python 3.10+ from https://www.python.org/downloads/ and make sure it is on PATH."
    exit 1
}

# ---------------------------------------------------------------------------
# 2. Create virtual environment
# ---------------------------------------------------------------------------
if (-not $SkipVenv) {
    Write-Step "Creating virtual environment at $VenvDir ..."
    if (Test-Path $VenvDir) {
        Write-Warn ".venv already exists — reusing."
    } else {
        & $PythonExe -m venv $VenvDir
        Write-OK "Virtual environment created."
    }
}

$PipExe    = Join-Path $VenvDir "Scripts\pip.exe"
$PythonVenv = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $PipExe)) {
    Write-Error "pip not found in $VenvDir\Scripts. Virtual environment may be broken."
    exit 1
}

# ---------------------------------------------------------------------------
# 3. Upgrade pip
# ---------------------------------------------------------------------------
Write-Step "Upgrading pip..."
& $PythonVenv -m pip install --upgrade pip | Out-Null
Write-OK "pip upgraded."

# ---------------------------------------------------------------------------
# 4. Install Python dependencies
# ---------------------------------------------------------------------------
Write-Step "Installing Python dependencies from requirements.txt..."
$ReqFile = Join-Path $RepoRoot "requirements.txt"
& $PipExe install -r $ReqFile
Write-OK "Dependencies installed."

# ---------------------------------------------------------------------------
# 5. Install mapfree in editable mode
# ---------------------------------------------------------------------------
Write-Step "Installing mapfree (editable)..."
& $PipExe install -e $RepoRoot
Write-OK "mapfree installed."

# ---------------------------------------------------------------------------
# 6. COLMAP notice
# ---------------------------------------------------------------------------
Write-Step "COLMAP (external binary)"
Write-Warn "COLMAP is NOT bundled. Install it separately:"
Write-Host "    - Installer: https://github.com/colmap/colmap/releases" -ForegroundColor White
Write-Host "    - Or see:    scripts\install_colmap_windows.md" -ForegroundColor White
Write-Host "    Add the COLMAP bin folder to PATH, or set MAPFREE_COLMAP_BIN=<path\to\colmap.bat>" -ForegroundColor White

# ---------------------------------------------------------------------------
# 7. Quick smoke test
# ---------------------------------------------------------------------------
Write-Step "Smoke test..."
$result = & $PythonVenv -c "import mapfree; print('import OK')" 2>&1
if ($result -match "import OK") {
    Write-OK "mapfree importable."
} else {
    Write-Warn "Import check failed: $result"
}

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "  MapFree installation complete!" -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Activate the virtual environment:" -ForegroundColor White
Write-Host "    .venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Run the GUI:" -ForegroundColor White
Write-Host "    mapfree gui" -ForegroundColor Yellow
Write-Host "    # or: run_mapfree.bat (double-click)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Run headless pipeline:" -ForegroundColor White
Write-Host "    mapfree run <image_folder> -o <output_folder>" -ForegroundColor Yellow
Write-Host ""
