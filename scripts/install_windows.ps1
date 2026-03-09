<#
.SYNOPSIS
    MapFree Engine — Windows Installer Script
.DESCRIPTION
    Installs all dependencies required to run MapFree on Windows:
      1. Checks for Administrator privileges (requests elevation if needed)
      2. Installs Chocolatey package manager (if not present)
      3. Installs COLMAP via Chocolatey (falls back to GitHub Releases)
      4. Installs Python 3.10+ (via Chocolatey if not found)
      5. Installs MapFree: pip install -e .
      6. Verifies installation with: mapfree --version
      7. Creates a Desktop shortcut for "MapFree GUI"
.NOTES
    Run in PowerShell as Administrator:
        Set-ExecutionPolicy Bypass -Scope Process -Force
        .\scripts\install_windows.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ─── Colours ──────────────────────────────────────────────────────────────────
function Write-Step   { param([string]$msg) Write-Host "  >> $msg" -ForegroundColor Cyan }
function Write-OK     { param([string]$msg) Write-Host "  OK  $msg" -ForegroundColor Green }
function Write-Warn   { param([string]$msg) Write-Host " WARN $msg" -ForegroundColor Yellow }
function Write-Fail   { param([string]$msg) Write-Host " FAIL $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "  ╔══════════════════════════════════╗" -ForegroundColor Blue
Write-Host "  ║  MapFree Engine — Installer      ║" -ForegroundColor Blue
Write-Host "  ╚══════════════════════════════════╝" -ForegroundColor Blue
Write-Host ""

# ─── 1. Administrator check ───────────────────────────────────────────────────
Write-Step "Checking Administrator privileges..."
$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warn "Not running as Administrator. Attempting to re-launch elevated..."
    $scriptPath = $MyInvocation.MyCommand.Path
    Start-Process powershell -Verb RunAs -ArgumentList (
        "-ExecutionPolicy Bypass -File `"$scriptPath`""
    )
    exit
}
Write-OK "Running as Administrator."

# ─── 2. Chocolatey ────────────────────────────────────────────────────────────
Write-Step "Checking for Chocolatey..."
if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
    Write-Step "Installing Chocolatey..."
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString(
        'https://community.chocolatey.org/install.ps1'
    ))
    # Reload PATH
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH", "User")
    Write-OK "Chocolatey installed."
} else {
    $chocoVer = (choco --version 2>&1) -join ""
    Write-OK "Chocolatey already installed ($chocoVer)."
}

# ─── 3. COLMAP ────────────────────────────────────────────────────────────────
Write-Step "Checking for COLMAP..."
$colmapPaths = @(
    "C:\tools\COLMAP\COLMAP.bat",
    "C:\tools\COLMAP\colmap.exe",
    (Get-Command colmap -ErrorAction SilentlyContinue)?.Source
) | Where-Object { $_ -and (Test-Path $_) }

if ($colmapPaths.Count -eq 0) {
    Write-Step "Installing COLMAP via Chocolatey..."
    $chocoResult = choco install colmap -y --no-progress 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "Chocolatey install failed. Downloading COLMAP from GitHub Releases..."

        $colmapDir = "C:\tools\COLMAP"
        New-Item -ItemType Directory -Path $colmapDir -Force | Out-Null

        $apiUrl = "https://api.github.com/repos/colmap/colmap/releases/latest"
        try {
            $release = Invoke-RestMethod -Uri $apiUrl -UseBasicParsing
            $asset = $release.assets | Where-Object { $_.name -match "windows.*zip" -or $_.name -match "win.*zip" } | Select-Object -First 1
            if ($asset) {
                $zipPath = "$env:TEMP\colmap_windows.zip"
                Write-Step "Downloading $($asset.name)..."
                Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath -UseBasicParsing
                Expand-Archive -Path $zipPath -DestinationPath $colmapDir -Force
                Write-OK "COLMAP extracted to $colmapDir"
            } else {
                Write-Warn "Could not find Windows COLMAP asset. Please install manually: https://colmap.github.io/install.html"
            }
        } catch {
            Write-Warn "Could not download COLMAP: $_"
            Write-Host "  Manual install: https://colmap.github.io/install.html" -ForegroundColor Yellow
        }
    } else {
        Write-OK "COLMAP installed via Chocolatey."
    }
} else {
    Write-OK "COLMAP found at: $($colmapPaths[0])"
}

# ─── 4. Python 3.10+ ─────────────────────────────────────────────────────────
Write-Step "Checking for Python 3.10+..."
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
$pythonOK = $false
if ($pythonCmd) {
    $pyVer = (python -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>&1).Trim()
    $parts = $pyVer -split "\."
    if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 10) {
        Write-OK "Python $pyVer found."
        $pythonOK = $true
    }
}
if (-not $pythonOK) {
    Write-Step "Installing Python 3.11 via Chocolatey..."
    choco install python311 -y --no-progress
    # Reload PATH
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH", "User")
    Write-OK "Python installed."
}

# ─── 5. MapFree Python package ────────────────────────────────────────────────
Write-Step "Installing MapFree Python package..."
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = Split-Path -Parent $scriptDir

if (Test-Path "$repoRoot\pyproject.toml") {
    Push-Location $repoRoot
    try {
        python -m pip install --upgrade pip --quiet
        python -m pip install -e ".[viewer]" --quiet
        Write-OK "MapFree installed in editable mode from $repoRoot"
    } finally {
        Pop-Location
    }
} else {
    Write-Step "Installing from PyPI (no local repo found)..."
    python -m pip install mapfree --quiet
    Write-OK "MapFree installed from PyPI."
}

# ─── 6. Verify ────────────────────────────────────────────────────────────────
Write-Step "Verifying installation..."
try {
    $ver = (mapfree --version 2>&1) -join ""
    Write-OK "mapfree --version: $ver"
} catch {
    Write-Warn "Could not run 'mapfree --version'. Ensure Python Scripts directory is on PATH."
}

# ─── 7. Desktop shortcut ──────────────────────────────────────────────────────
Write-Step "Creating Desktop shortcut..."
try {
    $pythonExe   = (Get-Command python).Source
    $desktopPath = [Environment]::GetFolderPath("Desktop")
    $shortcut    = "$desktopPath\MapFree GUI.lnk"

    $wsh  = New-Object -ComObject WScript.Shell
    $link = $wsh.CreateShortcut($shortcut)
    $link.TargetPath       = $pythonExe
    $link.Arguments        = "-m mapfree gui"
    $link.WorkingDirectory = $repoRoot
    $link.Description      = "MapFree Photogrammetry Engine"
    $link.Save()
    Write-OK "Desktop shortcut created: $shortcut"
} catch {
    Write-Warn "Could not create shortcut: $_"
}

# ─── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ╔══════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║  Installation complete!           ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "    1. Double-click 'MapFree GUI' on your Desktop" -ForegroundColor Gray
Write-Host "    2. Or run from terminal: mapfree gui" -ForegroundColor Gray
Write-Host "    3. Documentation: https://github.com/rnafulh-wq/MapFree#readme" -ForegroundColor Gray
Write-Host ""
