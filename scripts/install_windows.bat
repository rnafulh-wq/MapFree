@echo off
setlocal
cd /d "%~dp0.."
set "REPO_ROOT=%CD%"
set "LAUNCHER=%REPO_ROOT%\scripts\mapfree_launcher.bat"
echo ============================================
echo  MapFree Engine - Windows Installer
echo ============================================
echo.

REM --- Find conda ---
set CONDA_BASE=
for %%P in (
  "%USERPROFILE%\miniconda3"
  "%USERPROFILE%\anaconda3"
  "%LOCALAPPDATA%\miniconda3"
  "C:\ProgramData\miniconda3"
  "C:\ProgramData\anaconda3"
) do (
  if exist "%%~P\Scripts\conda.exe" (
    set "CONDA_BASE=%%~P"
    goto :found_conda
  )
)
echo ERROR: Conda tidak ditemukan.
echo Download Miniconda: https://docs.conda.io/en/latest/miniconda.html
pause
exit /b 1

:found_conda
set "CONDA_EXE=%CONDA_BASE%\Scripts\conda.exe"
echo [1/5] Conda ditemukan: %CONDA_EXE%
echo.

REM --- Create environment (PySide6 from conda-forge to avoid Qt DLL conflicts with COLMAP/GDAL) ---
echo [2/5] Membuat conda environment mapfree_engine...
call "%CONDA_EXE%" env remove -n mapfree_engine -y 2>nul
call "%CONDA_EXE%" env create -f environment.yml
if errorlevel 1 (
  echo ERROR: Gagal membuat environment.
  pause
  exit /b 1
)

REM --- Install MapFree (editable from repo) ---
echo [3/5] Installing MapFree...
call "%CONDA_EXE%" run -n mapfree_engine pip install -e .
if errorlevel 1 (
  echo ERROR: Gagal install MapFree.
  pause
  exit /b 1
)

REM --- Verifikasi semua deps ---
echo [4/5] Verifikasi instalasi...
call "%CONDA_EXE%" run -n mapfree_engine python -c "import mapfree; print('MapFree OK')"
if errorlevel 1 goto :verify_fail
call "%CONDA_EXE%" run -n mapfree_engine python -c "from osgeo import gdal; print('GDAL OK')"
if errorlevel 1 goto :verify_fail
call "%CONDA_EXE%" run -n mapfree_engine pdal --version
if errorlevel 1 goto :verify_fail
goto :verify_ok
:verify_fail
echo ERROR: Verifikasi gagal. Periksa pesan di atas.
pause
exit /b 1
:verify_ok

REM --- Desktop shortcut ---
echo [5/5] Membuat shortcut di Desktop...
set "DESKTOP=%USERPROFILE%\Desktop"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%DESKTOP%\MapFree.lnk'); $Shortcut.TargetPath = 'cmd.exe'; $Shortcut.Arguments = '/c \"\"%LAUNCHER%\"\"'; $Shortcut.WorkingDirectory = '%REPO_ROOT%'; $Shortcut.WindowStyle = 7; $Shortcut.IconLocation = 'cmd.exe,0'; $Shortcut.Description = 'MapFree Engine'; $Shortcut.Save()"
if errorlevel 1 (
  echo WARN: Shortcut gagal dibuat. Jalankan MapFree via scripts\mapfree_launcher.bat
) else (
  echo Shortcut: %DESKTOP%\MapFree.lnk
)

echo.
echo ============================================
echo  Instalasi selesai!
echo  Jalankan MapFree:
echo    - Double-click: Desktop ^> MapFree
echo    - Atau: scripts\mapfree_launcher.bat
echo ============================================
pause
