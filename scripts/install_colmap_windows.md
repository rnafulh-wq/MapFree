# Install COLMAP for Windows (MapFree)

## Phase 1 — Install COLMAP Windows binary

1. **Download** the latest stable Windows release:
   - **Release binaries:** https://github.com/colmap/colmap/releases (e.g. 3.13.0) — look for a Windows asset (e.g. `COLMAP-3.x-windows.zip` or similar from GitHub Actions / linked from [demuc.de/colmap](https://demuc.de/colmap/)).
   - Or **pre-release:** use the "Download Pre-Release Binaries" link on [demuc.de/colmap](https://demuc.de/colmap/).

2. **Extract** the archive so that one of these exists:
   - `C:\tools\COLMAP\COLMAP.bat`
   - or `C:\tools\COLMAP\colmap.exe`

   Create the folder if needed:
   ```powershell
   New-Item -ItemType Directory -Path "C:\tools\COLMAP" -Force
   ```
   Then extract the contents of the COLMAP zip into `C:\tools\COLMAP` (so that `COLMAP.bat` or `colmap.exe` is directly inside it).

3. **Verify:**
   ```powershell
   C:\tools\COLMAP\COLMAP.bat -h
   ```
   or
   ```powershell
   C:\tools\COLMAP\colmap.exe -h
   ```
   You should see the COLMAP help message without error.

4. **Optional:** Set environment variable to override the default path:
   ```powershell
   $env:MAPFREE_COLMAP = "C:\tools\COLMAP\COLMAP.bat"
   ```
   Or configure `colmap_path` in MapFree config (see config default or Settings).

After this, MapFree will find COLMAP automatically when you run the pipeline.
