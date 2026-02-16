# MapFree — Setup di Pop OS 24 LTS Nvidia

Panduan restore dan menjalankan MapFree di Pop OS 24 LTS (Nvidia).

## 1. Restore Project

```bash
mkdir -p ~/dev/mapfree
cd ~/dev/mapfree
tar -xzvf /path/to/mapfree_YYYYMMDD_HHMMSS.tar.gz -C .
```

Di Cursor: File → Open Folder → pilih folder yang sudah di-extract.

## 2. Requirements

| Komponen | Versi |
|----------|-------|
| OS | Pop OS 24.04 LTS Nvidia |
| Python | 3.10+ |
| COLMAP | 3.8+ (dengan CUDA) |
| NVIDIA Driver | Pre-installed di Pop Nvidia |
| PySide6 | via pip |

## 3. Install

### NVIDIA Driver
Pop OS Nvidia sudah include. Cek: `nvidia-smi`

### COLMAP (PPA)
```bash
sudo add-apt-repository ppa:savoury1/colmap
sudo apt update
sudo apt install colmap
```

### Python & MapFree
```bash
cd ~/dev/mapfree
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## 4. Verifikasi

```bash
colmap -h
nvidia-smi
mapfree run --help
```

## 5. Jalankan

```bash
mapfree run /path/to/images -o ./out_project
python gui/app.py  # GUI
```

## 6. Troubleshooting

- **nvidia-smi gagal**: Reboot setelah install driver
- **COLMAP tidak ketemu**: Pastikan di PATH (which colmap)
- **VRAM OOM**: Gunakan --force-profile LOW atau MAPFREE_CHUNK_SIZE=100
