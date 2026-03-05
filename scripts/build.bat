@echo off
REM MapFree — PyInstaller build for Windows (folder distribution).
REM Run from repo root: scripts\build.bat
REM Output: dist\MapFree\MapFree.exe

pip install pyinstaller
pyinstaller scripts/build_windows.spec --clean --noconfirm
echo.
echo Build selesai: dist\MapFree\MapFree.exe
echo.
