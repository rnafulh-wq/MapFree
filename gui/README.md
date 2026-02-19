# MapFree GUI

- **Desktop (native window):** `python -m gui.main` — requires GTK or Qt on Linux.
- **Browser only:** If the native window fails (e.g. missing GTK), the app opens in your default browser.

## Linux: native window (GTK)

Install system and Python deps, then run:

```bash
# System (Ubuntu/Debian/Pop!_OS)
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1

# Python
pip install pywebview[gtk]
```

Then: `python -m gui.main`
