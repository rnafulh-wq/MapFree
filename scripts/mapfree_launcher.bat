@echo off
setlocal

REM Cari conda di lokasi umum
set CONDA_PATHS=^
  %USERPROFILE%\miniconda3\Scripts\conda.exe ^
  %USERPROFILE%\anaconda3\Scripts\conda.exe ^
  %LOCALAPPDATA%\miniconda3\Scripts\conda.exe ^
  C:\ProgramData\miniconda3\Scripts\conda.exe ^
  C:\ProgramData\anaconda3\Scripts\conda.exe

for %%P in (%CONDA_PATHS%) do (
  if exist "%%P" (
    set CONDA_EXE=%%P
    goto :found_conda
  )
)

echo ERROR: Conda tidak ditemukan.
echo Install Miniconda dari https://docs.conda.io/en/latest/miniconda.html
pause
exit /b 1

:found_conda
REM Activate environment dan jalankan MapFree
call "%CONDA_EXE%" run -n mapfree_engine python -m mapfree %*
if errorlevel 1 (
  echo.
  echo ERROR: MapFree gagal dijalankan.
  echo Coba jalankan: conda activate mapfree_engine
  pause
)
