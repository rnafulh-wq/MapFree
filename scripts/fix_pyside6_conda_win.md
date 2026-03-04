# Fix PySide6 "DLL load failed" in conda env (Windows)

Error: `ImportError: DLL load failed while importing QtWidgets: The specified procedure could not be found.`

On Windows with conda, this can be caused by conda-forge’s PySide6 build (e.g. Python 3.12) or by running with `conda run` instead of an activated shell. Use **one** of the options below.

## Option A: New env with Python 3.11 + PySide6 from pip (recommended)

Conda-forge PySide6 on Python 3.12 sometimes hits this DLL error. A separate env with 3.11 and **pip** for PySide6 usually works:

```powershell
conda create -n mapfree_win2 python=3.11 -y
conda activate mapfree_win2
cd E:\dev\MapFree
pip install -r requirements.txt
pip install -e .
python -m mapfree
```

If that works, use `mapfree_win2` (and point `.vscode/settings.json` and `run_mapfree.bat` to it).

## Option B: Run from activated terminal (not `conda run`)

Sometimes the failure only happens with `conda run` because PATH/DLL search order differs. Try:

1. Open **Anaconda Prompt** (or a terminal where you’ve run `conda activate mapfree_win`).
2. Run:

   ```powershell
   conda activate mapfree_win
   cd E:\dev\MapFree
   python -m mapfree
   ```

If it works here but not via `conda run` or double-click, use this way to launch MapFree.

## Option C: Use PySide6 from conda-forge in current env

If you want to keep using conda-forge in `mapfree_win`:

```powershell
conda activate mapfree_win
conda install -c conda-forge pyside6 --force-reinstall -y
cd E:\dev\MapFree
pip install -e . --no-deps
python -m mapfree
```

## Option D: Pip-only in current env (if PySide6 was from conda)

```powershell
conda activate mapfree_win
conda remove pyside6 --force -y
pip install PySide6
pip install -r requirements.txt
pip install -e .
python -m mapfree
```

## If it still fails

- Install [Microsoft Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) (latest, x64).
- See which plugin/DLL fails:
  ```powershell
  $env:QT_DEBUG_PLUGINS=1; python -m mapfree
  ```
