# FASE v1.1 — Smart Installer & Hardware Detection
# Target: Juni 2026 | Prasyarat: v1.0.1 sudah rilis dan CI hijau

## TUJUAN
Membuat MapFree memiliki installer profesional seperti aplikasi Windows/Linux
pada umumnya — user tinggal klik Next → Next → Finish, semua dependency
terinstall otomatis sesuai hardware yang terdeteksi.

## STATUS LEGEND
# [ ] = Belum mulai
# [~] = Dalam progress  
# [x] = Selesai

---

## TASK 1.1 — Hardware Detection Module
**Priority: KRITIS**
**Cursor Prompt:**
```
Buat mapfree/utils/hardware_detector.py — module untuk deteksi hardware
yang dijalankan saat installer berjalan (SEBELUM MapFree diinstall).

Implementasi fungsi detect_system() -> dict yang mengembalikan:
{
  "os": "windows" | "linux" | "macos",
  "os_version": "Windows 11" | "Ubuntu 22.04" | ...,
  "cpu": {"name": str, "cores": int, "arch": "x64" | "arm64"},
  "ram_gb": float,
  "gpu": [
    {
      "name": str,           # "NVIDIA GeForce RTX 3060"
      "vendor": "nvidia" | "amd" | "intel" | "unknown",
      "vram_mb": int,
      "cuda_capable": bool,
      "cuda_version": str | None,   # "12.1" atau None
      "opencl_capable": bool
    }
  ],
  "recommended_profile": "high" | "medium" | "low" | "cpu_only",
  "recommended_colmap": "cuda" | "no_cuda",
  "recommended_openmvs": "cuda" | "opencl" | "cpu"
}

Logic recommended_profile:
- high: GPU Nvidia VRAM >= 8GB dan CUDA tersedia
- medium: GPU Nvidia VRAM 4-8GB atau AMD/Intel GPU
- low: GPU VRAM < 4GB
- cpu_only: tidak ada GPU sama sekali

Logic deteksi GPU (Windows):
- Jalankan: wmic path win32_VideoController get Name,AdapterRAM /format:csv
- Atau gunakan subprocess: nvidia-smi --query-gpu=name,memory.total,driver_version 
  --format=csv,noheader,nounits (jika ada nvidia-smi)
- Parse output untuk dapat nama dan VRAM

Logic deteksi GPU (Linux):
- Coba nvidia-smi untuk Nvidia
- Coba lspci | grep -i vga untuk semua GPU
- Coba glxinfo | grep "OpenGL renderer" untuk aktif GPU

Tambahkan unit test di tests/utils/test_hardware_detector.py:
- test_detect_system_returns_required_keys
- test_cpu_info_populated
- test_recommended_profile_cpu_only_when_no_gpu (mock wmic/nvidia-smi tidak ada)
- test_recommended_colmap_cuda_when_nvidia_available

Commit: "feat(utils): hardware detection module for installer"
```
- [x] hardware_detector.py dibuat
- [x] detect_system() mengembalikan semua field
- [x] Logic GPU detection untuk Windows
- [x] Logic GPU detection untuk Linux
- [x] recommended_profile logic benar
- [x] Unit test ditulis

---

## TASK 1.2 — Dependency Resolver
**Priority: KRITIS**
**Cursor Prompt:**
```
Buat mapfree/utils/dependency_resolver.py — module yang menentukan
dependency mana yang harus didownload berdasarkan hasil hardware_detector.

Implementasi:

class DependencyResolver:
    def __init__(self, system_info: dict):
        self.system = system_info
    
    def get_required_packages(self) -> list[DependencyPackage]:
        """Return list paket yang WAJIB diinstall."""
    
    def get_optional_packages(self) -> list[DependencyPackage]:
        """Return list paket opsional (OpenMVS, PDAL, GDAL)."""
    
    def get_colmap_download_url(self) -> str:
        """Return URL COLMAP yang tepat berdasarkan GPU."""
        # Jika CUDA tersedia → return URL colmap-cuda
        # Jika tidak → return URL colmap-no-cuda
        # URL dari GitHub Releases COLMAP terbaru

@dataclass
class DependencyPackage:
    name: str
    version: str
    download_url: str
    install_size_mb: int
    required: bool
    install_method: str  # "zip_extract" | "exe_silent" | "choco" | "apt" | "conda"
    install_args: list[str]  # argumen untuk silent install
    verify_command: str  # command untuk verifikasi setelah install
    path_to_add: str | None  # path yang perlu ditambah ke PATH

Packages yang perlu didefinisikan:
- COLMAP (cuda variant & no-cuda variant) — zip_extract ke C:\MapFree\deps\colmap\
- OpenMVS (opsional) — zip_extract ke C:\MapFree\deps\openmvs\
- PDAL (opsional, Windows) — conda install atau MSI
- GDAL (opsional, Windows) — conda install atau wheel

Semua dependency di-extract ke: C:\MapFree\deps\ (Windows) atau ~/.mapfree/deps/ (Linux)
MapFree harus update PATH-nya sendiri saat startup agar deps terdeteksi.

Commit: "feat(utils): dependency resolver based on hardware profile"
```
- [x] DependencyResolver class dibuat
- [x] DependencyPackage dataclass lengkap
- [x] URL COLMAP (cuda & no-cuda) dikonfigurasi
- [x] Logic pemilihan package berdasarkan GPU
- [x] Unit test ditulis

---

## TASK 1.3 — Downloader dengan Progress
**Priority: KRITIS**
**Cursor Prompt:**
```
Buat mapfree/utils/dependency_downloader.py — module untuk download
dependency dengan progress tracking.

Implementasi:

class DependencyDownloader:
    def download(
        self,
        package: DependencyPackage,
        dest_dir: Path,
        progress_callback: Callable[[int, int], None] | None = None
        # progress_callback(bytes_downloaded, total_bytes)
    ) -> Path:
        """Download package, return path ke file yang didownload."""
    
    def install(self, package: DependencyPackage, downloaded_file: Path) -> bool:
        """Install package setelah download selesai."""
    
    def verify(self, package: DependencyPackage) -> bool:
        """Verifikasi instalasi berhasil dengan menjalankan verify_command."""

Implementasi download:
- Gunakan urllib.request atau requests dengan stream=True
- Tampilkan progress via callback (bytes downloaded / total)
- Support resume download jika file sudah ada sebagian (range request)
- Timeout 30 detik untuk koneksi, 300 detik untuk download
- Retry 3x jika gagal dengan exponential backoff

Implementasi install per method:
- zip_extract: extract ZIP ke dest_dir, update PATH di mapfree config
- exe_silent: jalankan .exe dengan /S /quiet flags
- choco: subprocess ["choco", "install", name, "-y", "--no-progress"]
- apt: subprocess ["sudo", "apt", "install", "-y", name]

Tambahkan tests/utils/test_dependency_downloader.py:
- test_download_with_mock_server (gunakan pytest httpserver atau mock urllib)
- test_progress_callback_called
- test_retry_on_failure
- test_verify_success
- test_verify_failure

Commit: "feat(utils): dependency downloader with progress and retry"
```
- [x] DependencyDownloader class dibuat
- [x] Download dengan progress callback
- [x] Resume support
- [x] Retry dengan exponential backoff
- [x] Install per method diimplementasi
- [x] Unit test ditulis

---

## TASK 1.4 — Windows Installer (Inno Setup)
**Priority: KRITIS**
**Cursor Prompt:**
```
Buat Windows installer profesional menggunakan Inno Setup.

1. Install Inno Setup di CI: download dari https://jrsoftware.org/isdl.php
   Atau gunakan chocolatey: choco install innosetup -y

2. Buat scripts/installer/mapfree_setup.iss — Inno Setup script:

[Setup]
AppName=MapFree Engine
AppVersion=1.1.0
AppPublisher=MapFree
DefaultDirName={autopf}\MapFree
DefaultGroupName=MapFree
OutputBaseFilename=MapFree-Setup-1.1.0
SetupIconFile=mapfree\gui\resources\icons\mapfree.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "indonesian"; MessagesFile: "compiler:Languages\Indonesian.isl"

[Tasks]
Name: "desktopicon"; Description: "Buat shortcut di Desktop"; GroupDescription: "Shortcut:"; Flags: unchecked
Name: "startmenuicon"; Description: "Tambahkan ke Start Menu"; GroupDescription: "Shortcut:"; Flags: checkedonce

[Files]
; MapFree app (hasil PyInstaller build)
Source: "dist\MapFree\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\MapFree Engine"; Filename: "{app}\MapFree.exe"
Name: "{userdesktop}\MapFree Engine"; Filename: "{app}\MapFree.exe"; Tasks: desktopicon

[Run]
; Jalankan MapFree pertama kali setelah install selesai
; MapFree akan deteksi hardware dan download deps sendiri
Filename: "{app}\MapFree.exe"; Description: "Jalankan MapFree Engine"; Flags: postinstall nowait skipifsilent

[Code]
// Pascal script untuk hardware detection SEBELUM install
// Tampilkan halaman custom: "Hardware terdeteksi: GPU Anda = X, akan download COLMAP Y"
// User bisa uncheck dependency yang tidak diinginkan

3. Tambahkan custom wizard page di [Code] section:
   - Halaman "Deteksi Hardware" — jalankan hardware_detector via embedded Python
     atau pre-generate hardware_info.json saat build
   - Halaman "Pilih Komponen" — checkbox untuk:
     ✅ COLMAP (Wajib) — versi CUDA atau no-CUDA otomatis dipilih
     ☐ OpenMVS (Opsional, untuk mesh berkualitas tinggi)  
     ☐ PDAL + GDAL (Opsional, untuk DTM dan orthophoto)
   - Tampilkan total download size berdasarkan pilihan

4. Update .github/workflows/release.yml:
   - Setelah PyInstaller build, jalankan Inno Setup compiler
   - Upload MapFree-Setup-1.1.0.exe ke GitHub Releases
   - Upload juga MapFree-windows-portable.zip (untuk yang tidak mau installer)

Commit: "build: add Inno Setup Windows installer with hardware detection page"
```
- [x] mapfree_setup.iss dibuat
- [x] Custom wizard pages: hardware detection + component selection
- [x] COLMAP variant otomatis dipilih berdasarkan GPU
- [x] Shortcut Desktop dan Start Menu dibuat
- [x] Build CI menghasilkan .exe installer
- [ ] Installer berjalan di Windows 10/11 fresh

---

## TASK 1.5 — Linux Installer (Shell Script + AppImage)
**Priority: TINGGI**
**Cursor Prompt:**
```
Buat Linux installer yang proper dengan dua mode:

MODE 1 — Interactive Shell Installer:
Buat scripts/installer/install_linux.sh:

#!/bin/bash
set -e

echo "╔══════════════════════════════════════╗"
echo "║     MapFree Engine Installer v1.1    ║"
echo "╚══════════════════════════════════════╝"

# Deteksi distro
detect_distro() { ... }  # Ubuntu/Debian/Arch/Fedora

# Deteksi GPU
detect_gpu() {
  if command -v nvidia-smi &>/dev/null; then
    echo "nvidia"
  elif lspci | grep -qi "amd"; then
    echo "amd"  
  else
    echo "cpu"
  fi
}

# Tampilkan hardware summary
GPU=$(detect_gpu)
RAM=$(free -g | awk '/^Mem:/{print $2}')
echo "Hardware terdeteksi:"
echo "  GPU: $GPU"
echo "  RAM: ${RAM}GB"
echo ""

# Tanya user konfirmasi install
echo "Akan diinstall:"
echo "  [✓] MapFree Engine"
echo "  [✓] COLMAP ($([ "$GPU" = "nvidia" ] && echo "CUDA" || echo "CPU"))"
read -p "Lanjutkan? [Y/n] " confirm

# Install COLMAP
install_colmap() {
  if [ "$GPU" = "nvidia" ]; then
    sudo apt install -y colmap  # atau download binary CUDA
  else
    sudo apt install -y colmap
  fi
}

# Install ke ~/.local/bin/mapfree atau /opt/mapfree
# Buat .desktop file untuk app launcher
# Tambahkan ke PATH

MODE 2 — AppImage (sudah berjalan dari v1.0):
Update AppImage agar saat PERTAMA KALI dijalankan:
1. Tampilkan dialog "First Run Setup"
2. Deteksi hardware
3. Tawari download COLMAP ke ~/.mapfree/deps/
4. Simpan flag di ~/.mapfree/setup_complete.json

Buat scripts/installer/create_desktop_entry.sh:
- Buat ~/.local/share/applications/mapfree.desktop
- Buat ~/.local/share/icons/mapfree.png
- Jalankan update-desktop-database

Commit: "build: add Linux shell installer with hardware detection"
```
- [ ] install_linux.sh dibuat
- [ ] Hardware detection (GPU, RAM, distro)
- [ ] COLMAP install sesuai GPU
- [ ] .desktop file dibuat (app muncul di app launcher)
- [ ] First-run setup di AppImage diimplementasi

---

## TASK 1.6 — First Run Setup Wizard di dalam MapFree
**Priority: KRITIS**
**Cursor Prompt:**
```
Buat mapfree/gui/dialogs/first_run_wizard.py — QWizard dengan 4 halaman:

PAGE 1 — Selamat Datang:
- Logo MapFree besar
- Teks: "Selamat datang di MapFree Engine v1.1"
- "Wizard ini akan mendeteksi hardware Anda dan menginstall komponen yang diperlukan."
- Tombol: Mulai Setup

PAGE 2 — Deteksi Hardware (otomatis berjalan):
- Progress spinner sambil hardware_detector.detect_system() berjalan
- Setelah selesai tampilkan tabel:
  | Komponen | Hasil |
  | CPU      | Intel Core i7-12700H (14 cores) |
  | RAM      | 32 GB |
  | GPU      | NVIDIA RTX 3060 (6GB VRAM) |
  | CUDA     | 12.1 tersedia |
  | Profil   | Medium (CUDA) |
- Tombol: Lanjutkan

PAGE 3 — Pilih Komponen:
- QTreeWidget dengan checkbox:
  ✅ COLMAP 3.9 (CUDA) — Wajib — ~180 MB download
     Dioptimalkan untuk GPU NVIDIA Anda
  ☐ OpenMVS — Opsional — ~85 MB download  
     Untuk mesh 3D berkualitas tinggi
  ☐ PDAL + GDAL — Opsional — ~120 MB download
     Untuk output DTM dan orthophoto
- Label: "Total download: XXX MB"
- Tombol: Install Sekarang

PAGE 4 — Instalasi:
- QProgressBar keseluruhan (0-100%)
- Per-package progress:
  [COLMAP    ] ████████░░ 80% — Downloading... (145/180 MB)
  [OpenMVS   ] ░░░░░░░░░░ Menunggu...
  [PDAL+GDAL ] ░░░░░░░░░░ Menunggu...
- Log area (QTextEdit, read-only) untuk menampilkan status real-time
- Tombol Cancel (berhenti graceful, deps yang sudah didownload disimpan)
- Setelah selesai: tombol "Selesai & Buka MapFree"

Integrasi ke main_window.py:
- Cek ~/.mapfree/setup_complete.json saat startup
- Jika tidak ada atau deps berubah → tampilkan FirstRunWizard
- Jika sudah ada → skip wizard, langsung buka main window

Commit: "feat(gui): first run setup wizard with hardware detection and auto-download"
```
- [ ] FirstRunWizard QWizard dibuat (4 halaman)
- [ ] Hardware detection page berjalan async
- [ ] Component selection dengan checkbox dan size calculation
- [ ] Download + install page dengan dual progress bar
- [ ] setup_complete.json tersimpan setelah wizard selesai
- [ ] Main window skip wizard jika sudah setup

---

## TASK 1.7 — PATH Management
**Priority: TINGGI**
**Cursor Prompt:**
```
Buat mapfree/utils/path_manager.py — module untuk manage PATH
agar MapFree selalu bisa menemukan dependency yang diinstall.

Implementasi:

class PathManager:
    DEPS_DIR_WINDOWS = Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "MapFree" / "deps"
    DEPS_DIR_LINUX = Path.home() / ".mapfree" / "deps"
    
    @classmethod
    def get_deps_dir(cls) -> Path:
        """Return direktori deps sesuai OS."""
    
    @classmethod
    def register_dep(cls, name: str, bin_path: Path):
        """Simpan lokasi binary ke ~/.mapfree/deps_registry.json"""
    
    @classmethod
    def get_dep_path(cls, name: str) -> Path | None:
        """Return path ke binary berdasarkan registry."""
    
    @classmethod  
    def inject_to_env(cls):
        """Tambahkan semua deps ke os.environ['PATH'] saat startup MapFree."""
        # Baca deps_registry.json
        # Tambahkan semua bin_path ke PATH
        # Ini dipanggil di mapfree/app.py SEBELUM apapun dijalankan

    @classmethod
    def add_to_system_path_windows(cls, path: str):
        """Tambahkan path ke System PATH di registry Windows (butuh admin)."""
        import winreg
        # Edit HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment

Panggil PathManager.inject_to_env() di:
1. mapfree/app.py — baris pertama sebelum import lain
2. mapfree/cli/main.py — baris pertama

Update dependency_check.py:
- Sebelum cek PATH sistem, cek PathManager.get_dep_path() dulu
- Ini memastikan deps yang diinstall MapFree Wizard terdeteksi
  meski belum ada di system PATH

Commit: "feat(utils): path manager for MapFree-managed dependencies"
```
- [ ] PathManager class dibuat
- [ ] deps_registry.json persistence
- [ ] inject_to_env() dipanggil di app.py dan cli
- [ ] System PATH update untuk Windows
- [ ] dependency_check.py diupdate untuk cek registry dulu

---

## TASK 1.8 — Update CI/CD untuk Installer Build
**Priority: TINGGI**
**Cursor Prompt:**
```
Update .github/workflows/release.yml untuk build installer:

Job build-windows-installer (setelah build-windows):
  runs-on: windows-latest
  needs: build-windows
  steps:
    - uses: actions/checkout@v4
    - name: Download Windows artifact
      uses: actions/download-artifact@v4
      with:
        name: windows
        path: dist/MapFree/
    - name: Install Inno Setup
      run: choco install innosetup -y
    - name: Build installer
      run: iscc scripts/installer/mapfree_setup.iss
    - name: Upload installer artifact
      uses: actions/upload-artifact@v4
      with:
        name: windows-installer
        path: Output/MapFree-Setup-*.exe

Job create-release (update untuk include installer):
  - Download windows-installer artifact
  - Upload MapFree-Setup-1.1.0.exe ke GitHub Release
  - Beri label yang jelas di release notes:
    "📦 MapFree-Setup-1.1.0.exe — Installer Windows (Recommended)"
    "🗜️ MapFree-windows-portable.zip — Portable (tanpa installer)"
    "🐧 MapFree-x86_64.AppImage — Linux"

Update CHANGELOG.md untuk v1.1.0 saat semua task selesai.

Commit: "ci: add Inno Setup installer build to release workflow"
```
- [ ] build-windows-installer job ditambahkan
- [ ] Inno Setup berjalan di CI
- [ ] Installer .exe ter-upload ke GitHub Releases
- [ ] Release notes mencantumkan semua format download

---

## CHECKLIST AKHIR v1.1.0

### Installer Windows
- [ ] MapFree-Setup-1.1.0.exe berjalan di Windows 10/11 fresh
- [ ] Wizard mendeteksi GPU dengan benar
- [ ] COLMAP CUDA diinstall jika Nvidia terdeteksi
- [ ] COLMAP no-CUDA diinstall jika tidak ada Nvidia
- [ ] Shortcut Desktop dan Start Menu terbuat
- [ ] MapFree langsung bisa run pipeline setelah install

### Installer Linux
- [ ] install_linux.sh berjalan di Ubuntu 22.04
- [ ] AppImage first-run wizard berfungsi
- [ ] .desktop file terbuat (muncul di app launcher GNOME/KDE)
- [ ] COLMAP terinstall otomatis

### First Run Wizard
- [ ] 4 halaman wizard tampil dengan benar
- [ ] Hardware detection akurat (CPU, RAM, GPU, CUDA)
- [ ] Download progress real-time
- [ ] setup_complete.json tersimpan
- [ ] Wizard tidak muncul lagi setelah setup selesai

### PATH Management
- [ ] deps di-inject ke PATH saat MapFree startup
- [ ] dependency_check.py mendeteksi deps dari registry
- [ ] Pipeline bisa jalan tanpa user setup PATH manual
