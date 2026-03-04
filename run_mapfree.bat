@echo off
REM Cara paling simpel buka MapFree: double-click run_mapfree.bat
REM Harus activate env dulu (jangan conda run) supaya PySide6/Qt DLL bisa diload.

set "CONDA_ROOT=%USERPROFILE%\miniconda3"
if not exist "%CONDA_ROOT%" set "CONDA_ROOT=%USERPROFILE%\anaconda3"
call "%CONDA_ROOT%\Scripts\activate.bat" mapfree_win 2>nul
if errorlevel 1 (
  echo Gagal activate conda env mapfree_win. Pastikan Miniconda/Anaconda terpasang dan env mapfree_win ada.
  pause
  exit /b 1
)

cd /d "%~dp0"
python -m mapfree
if errorlevel 1 pause
