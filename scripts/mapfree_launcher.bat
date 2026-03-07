@echo off
setlocal
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
    goto :found
  )
)
echo ERROR: Conda tidak ditemukan.
pause
exit /b 1

:found
call "%CONDA_BASE%\Scripts\activate.bat" mapfree_engine
python -m mapfree %*
if errorlevel 1 pause
