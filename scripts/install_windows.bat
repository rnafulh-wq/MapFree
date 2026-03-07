@echo off
setlocal
cd /d "%~dp0.."
echo ============================================
echo  MapFree Engine - Windows Installer
echo ============================================
echo.

REM Cari conda
set CONDA_PATHS=^
  %USERPROFILE%\miniconda3\Scripts\conda.exe ^
  %USERPROFILE%\anaconda3\Scripts\conda.exe ^
  %LOCALAPPDATA%\miniconda3\Scripts\conda.exe ^
  C:\ProgramData\miniconda3\Scripts\conda.exe

for %%P in (%CONDA_PATHS%) do (
  if exist "%%P" (
    set CONDA_EXE=%%P
    goto :found_conda
  )
)

echo ERROR: Conda tidak ditemukan.
echo Download Miniconda: https://docs.conda.io/en/latest/miniconda.html
pause
exit /b 1

:found_conda
echo [1/4] Conda ditemukan: %CONDA_EXE%
echo.

REM Hapus environment lama jika ada
echo [2/4] Membuat conda environment mapfree_engine...
call "%CONDA_EXE%" env remove -n mapfree_engine -y 2>nul
call "%CONDA_EXE%" env create -f environment.yml
if errorlevel 1 (
  echo ERROR: Gagal membuat environment.
  pause
  exit /b 1
)

REM Install MapFree ke environment (editable dari repo)
echo [3/4] Installing MapFree...
call "%CONDA_EXE%" run -n mapfree_engine pip install -e .
if errorlevel 1 (
  echo ERROR: Gagal install MapFree.
  pause
  exit /b 1
)

REM Verifikasi
echo [4/4] Verifikasi instalasi...
call "%CONDA_EXE%" run -n mapfree_engine python -c "import mapfree; print('MapFree OK')"
call "%CONDA_EXE%" run -n mapfree_engine python -c "from osgeo import gdal; print('GDAL OK')"
call "%CONDA_EXE%" run -n mapfree_engine pdal --version

echo.
echo ============================================
echo  Instalasi selesai!
echo  Jalankan MapFree: scripts\mapfree_launcher.bat
echo ============================================
pause
