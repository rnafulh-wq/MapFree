# MapFree Engine — Roadmap & Architectural Vision
*Dokumen ini menggabungkan visi arsitektur jangka panjang dengan roadmap pengembangan bertahap.*
*Dibuat: 2026-03-06*

---

## VISI PRODUK

MapFree Engine adalah platform photogrammetry open-source berbasis Python yang:
- **Mudah digunakan** — GUI profesional setara Metashape untuk pengguna lapangan
- **Dapat diperluas** — Plugin system untuk peneliti dan developer
- **Modular** — Setiap komponen dapat diganti atau dikembangkan mandiri
- **Cross-platform** — Windows, Linux, macOS

---

## ARSITEKTUR TARGET

### Layered Architecture

```
┌─────────────────────────────────────────────┐
│                  GUI Layer                  │
│         (PyQt/PySide — mapfree/gui/)        │
└──────────────────┬──────────────────────────┘
                   │ API Bridge
┌──────────────────▼──────────────────────────┐
│             Application Layer               │
│    (Services — mapfree/services/)           │
│  ReconstructionService, ProjectService      │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│             Core Domain Layer               │
│         (mapfree/core/)                     │
│  Project │ Pipeline │ Job │ Config │ Errors │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│              Engine Layer                   │
│         (mapfree/engines/)                  │
│    COLMAP │ OpenMVG │ OpenMVS │ Registry    │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│         External Tools                      │
│   colmap.exe │ OpenMVG │ OpenMVS │ PDAL     │
└─────────────────────────────────────────────┘
```

### Data Flow

```
GUI
 ↓ (user action: klik Run)
ReconstructionService
 ↓ (buat Job)
Pipeline
 ↓ (jalankan Stage per Stage)
Stage (Feature Extraction, Matching, ...)
 ↓ (panggil engine)
Engine (COLMAP, OpenMVG, ...)
 ↓ (subprocess)
External Tool (colmap.exe)
```

---

## STRUKTUR FOLDER TARGET

```
mapfree/
│
├── core/                          ← Core Domain (pure Python, no I/O)
│   ├── project/
│   │   ├── project.py             ← Project dataclass
│   │   ├── project_manager.py     ← CRUD project
│   │   └── paths.py               ← ProjectPaths (folder structure)
│   │
│   ├── pipeline/
│   │   ├── pipeline.py            ← Pipeline orchestrator
│   │   ├── stage.py               ← BaseStage abstract class
│   │   └── stages/
│   │       ├── feature_extraction.py
│   │       ├── matching.py
│   │       ├── sparse_reconstruction.py
│   │       ├── dense_reconstruction.py
│   │       └── geospatial.py
│   │
│   ├── job/
│   │   ├── job.py                 ← Job (kumpulan Task)
│   │   ├── task.py                ← Task (unit kerja terkecil)
│   │   └── progress.py            ← Progress tracking
│   │
│   ├── config/
│   │   └── config.py              ← ProjectConfig, PipelineConfig
│   │
│   └── errors/
│       └── exceptions.py          ← Semua custom exceptions
│
├── engines/
│   ├── base_engine.py             ← AbstractEngine interface
│   ├── registry.py                ← EngineRegistry (discovery)
│   │
│   ├── colmap/
│   │   ├── engine.py              ← ColmapEngine
│   │   ├── commands.py            ← CommandBuilder
│   │   └── parser.py              ← Output parser
│   │
│   ├── openmvg/
│   │   ├── engine.py
│   │   └── commands.py
│   │
│   └── openmvs/
│       ├── engine.py
│       └── commands.py
│
├── services/
│   ├── reconstruction_service.py  ← Orchestrate pipeline end-to-end
│   ├── project_service.py         ← Project CRUD + import images
│   └── export_service.py          ← Export hasil ke format lain
│
├── gui/
│   ├── api_bridge.py              ← GUI ↔ Service bridge (signals/slots)
│   ├── main_window.py
│   ├── panels/
│   │   ├── dataset_panel.py
│   │   ├── viewer_panel.py
│   │   └── output_panel.py
│   └── dialogs/
│       ├── setup_dialog.py
│       └── export_dialog.py
│
├── plugins/                       ← Plugin system
│   ├── base_plugin.py
│   ├── loader.py
│   └── builtin/
│
├── utils/                         ← Utilities (stateless helpers)
│
└── logging/                       ← Logging system
    ├── logger.py
    └── handlers.py
```

---

## ROADMAP PENGEMBANGAN

---

### v1.1.1 — Bug Fix & UX (SEKARANG)
*Target: Segera, sebelum release v1.1.0*

**Focus: Perbaiki masalah dari real-world testing**

| Task | Deskripsi | Priority |
|------|-----------|----------|
| A | Fix COLMAP detection — robust executable finder | KRITIS |
| B | Skip setup dialog jika dependency sudah verified | TINGGI |
| C | Responsive GUI layout (QSplitter) | MEDIUM |
| D | Output folder structure ala Metashape | MEDIUM |
| E | Import foto: pilih file individual (multi-select) | MEDIUM |

Detail: lihat `fase_v1.1.1_bugfix_ux.md`

**Definition of Done:**
- [ ] Pipeline berhasil end-to-end dengan 335 foto Lewoleba
- [ ] Sparse → Dense → DTM → Ortho → Output selesai tanpa error
- [ ] Single installer: install sekali, langsung jalan di Windows baru
- [ ] environment.yml lengkap: semua deps di mapfree_engine
- [ ] scripts/install_windows.bat: auto-detect conda, create env, install MapFree
- [ ] scripts/mapfree_launcher.bat: jalankan MapFree tanpa manual activate conda
- [ ] find_tool() portable: cari GDAL/PDAL dari sys.executable, bukan hardcode path
- [ ] Test install dari nol di folder baru (bukan dev environment)
- [ ] Release v1.1.0 tersedia di GitHub

---

### v1.2 — Core Architecture Refactor
*Target: Q2 2026*

**Focus: Refactor ke Layered Architecture yang benar**

#### v1.2.1 — Core Domain Layer

```
Buat mapfree/core/project/ — Project System

Project dataclass:
  - id: str (UUID)
  - name: str  
  - created_at: datetime
  - images: list[ImageFile]
  - config: ProjectConfig
  - paths: ProjectPaths

ProjectPaths:
  - root, images, sparse, dense, mesh, geospatial, exports, logs

ProjectManager:
  - create(name, output_dir) -> Project
  - load(project_file) -> Project
  - save(project) -> None
  - import_images(project, paths) -> int  ← jumlah foto ditambahkan
```

- [ ] `mapfree/core/project/project.py` — Project dataclass
- [ ] `mapfree/core/project/paths.py` — ProjectPaths (folder structure)
- [ ] `mapfree/core/project/project_manager.py` — CRUD
- [ ] Tests: 90%+ coverage
- [ ] Migrate dari kode project lama

#### v1.2.2 — Job System

```
Buat mapfree/core/job/ — Job/Task System

Job:
  - id, name, project_id
  - tasks: list[Task]
  - status: pending | running | done | failed
  - created_at, started_at, finished_at
  - progress: JobProgress

Task:
  - id, name, job_id
  - stage: str  (feature_extraction, matching, ...)
  - status: TaskStatus
  - log_file: Path
  - result: dict | None

JobProgress:
  - current_task: int
  - total_tasks: int
  - percent: float
  - eta_seconds: int | None
  - on_progress: Callable  ← callback ke GUI
```

- [ ] `mapfree/core/job/job.py`
- [ ] `mapfree/core/job/task.py`
- [ ] `mapfree/core/job/progress.py`
- [ ] Progress callback ke GUI via signal
- [ ] Tests: 90%+ coverage

#### v1.2.3 — Engine Abstraction

```
Buat mapfree/engines/ — Engine Layer

AbstractEngine interface:
  - name: str
  - is_available() -> bool
  - get_version() -> str | None
  - run(command: EngineCommand) -> EngineResult

CommandBuilder pattern:
  # Sebelum (saat ini):
  subprocess.run(["colmap", "feature_extractor", "--image_path", ...])

  # Sesudah (target):
  cmd = ColmapCommands.feature_extraction(
      image_path=paths.images,
      database_path=paths.sparse / "database.db",
      quality="medium"
  )
  result = engine.run(cmd)

EngineRegistry:
  - register(engine)
  - get(name) -> AbstractEngine
  - list_available() -> list[str]
```

- [ ] `mapfree/engines/base_engine.py` — AbstractEngine
- [ ] `mapfree/engines/colmap/commands.py` — CommandBuilder
- [ ] `mapfree/engines/colmap/parser.py` — Output parser
- [ ] `mapfree/engines/registry.py` — EngineRegistry
- [ ] Migrate ColmapEngine ke struktur baru
- [ ] Tests: mock subprocess calls

#### v1.2.3a — Dynamic Argument Validation ← TAMBAHAN dari real-world testing
*Latar belakang: COLMAP 3.13 mengubah banyak nama argumen dari versi sebelumnya,
menyebabkan pipeline crash. Fix manual tidak scalable karena setiap versi COLMAP
bisa mengubah nama argumen kapan saja.*

```
Buat mapfree/engines/colmap/arg_validator.py:

class ColmapArgValidator:
    def __init__(self, colmap_exe: Path):
        self._cache_path = Path.home() / ".mapfree/colmap_args_cache.json"
        self._valid_args = self._load_or_build_cache(colmap_exe)
    
    def _parse_help(self, colmap_exe, command) -> set[str]:
        # Jalankan: colmap <command> --help
        # Parse semua baris yang dimulai dengan "--"
        # Return set nama argumen yang valid
        result = subprocess.run(
            [str(colmap_exe), command, "--help"],
            capture_output=True, text=True, timeout=10
        )
        args = set()
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("--"):
                arg = line.split()[0]  # ambil "--ArgName.subname"
                args.add(arg)
        return args
    
    def _load_or_build_cache(self, exe) -> dict[str, set]:
        # Load dari cache jika ada dan tidak expired (7 hari)
        # Jika tidak ada, build dari --help untuk semua command
        commands = ["feature_extractor", "spatial_matcher", 
                   "exhaustive_matcher", "sequential_matcher", "mapper"]
        cache = {}
        for cmd in commands:
            cache[cmd] = self._parse_help(exe, cmd)
        return cache
    
    def filter_args(self, command: str, proposed_args: dict) -> list:
        # Hanya return argumen yang valid untuk command ini
        valid = self._valid_args.get(command, set())
        result = []
        for arg, value in proposed_args.items():
            if arg in valid:
                result += [arg, str(value)]
            else:
                logger.warning(
                    f"COLMAP arg '{arg}' tidak valid untuk '{command}', dilewati. "
                    f"Mungkin versi COLMAP berubah."
                )
        return result

Integrasi di ColmapEngine.__init__():
    self._validator = ColmapArgValidator(self._colmap_exe)

Integrasi di setiap command builder:
    # Propose semua argumen yang ingin dipakai
    proposed = {
        "--ImageReader.single_camera": "1",
        "--SiftExtraction.max_num_features": "4096",
        "--FeatureExtraction.use_gpu": str(use_gpu),
        # ... semua argumen
    }
    # Filter hanya yang valid untuk versi COLMAP ini
    validated_args = self._validator.filter_args("feature_extractor", proposed)
    cmd = [str(colmap_exe), "feature_extractor", 
           "--database_path", str(db), ...] + validated_args
```

Manfaat:
- MapFree kompatibel dengan COLMAP 3.8, 3.9, 3.13, dan versi masa depan
- Tidak perlu update manual setiap kali COLMAP rilis versi baru
- Warning informatif jika argumen dilewati
- Cache hasil --help agar tidak lambat setiap startup

- [ ] `mapfree/engines/colmap/arg_validator.py` — ColmapArgValidator
- [ ] Cache valid args ke `~/.mapfree/colmap_args_cache.json`
- [ ] Integrasi ke semua command di ColmapEngine
- [ ] Invalidate cache jika versi COLMAP berubah
- [ ] Tests: mock subprocess --help output untuk berbagai versi

#### v1.2.4 — Service Layer

```
Buat mapfree/services/ — Application Services

ReconstructionService:
  - start(project, config) -> Job
  - pause(job_id) -> None
  - resume(job_id) -> None
  - cancel(job_id) -> None
  - get_status(job_id) -> JobProgress

ProjectService:
  - create_project(name, output_dir) -> Project
  - open_project(path) -> Project
  - import_images(project, file_paths) -> ImportResult
  - export_results(project, format) -> Path

GUI hanya boleh memanggil Service, tidak boleh langsung ke Engine atau Pipeline.
```

- [ ] `mapfree/services/reconstruction_service.py`
- [ ] `mapfree/services/project_service.py`
- [ ] `mapfree/gui/api_bridge.py` — Qt signals antara GUI dan Service
- [ ] GUI refactor: hapus direct import ke core/engine
- [ ] Tests: integration tests per service

---

### v1.3 — Pipeline System Upgrade
*Target: Q3 2026*

**Focus: Pipeline yang fleksibel dan resumable**

#### Stage System

```
BaseStage:
  - name: str
  - description: str
  - required_inputs: list[str]   ← validasi sebelum run
  - outputs: list[str]           ← validasi setelah run
  - run(context: StageContext) -> StageResult

StageContext:
  - project: Project
  - paths: ProjectPaths
  - config: PipelineConfig
  - job: Job
  - engine: AbstractEngine

Pipeline:
  - stages: list[BaseStage]
  - add_stage(stage)
  - remove_stage(name)
  - run(context) → asyncio-based
  - resume(from_stage) — skip stages yang sudah done
```

**Stages yang diimplementasi:**
- [ ] FeatureExtractionStage
- [ ] MatchingStage
- [ ] SparseReconstructionStage
- [ ] DenseReconstructionStage (COLMAP atau OpenMVS)
- [ ] MeshReconstructionStage
- [ ] TexturingStage
- [ ] GeospatialStage (DTM, Orthomosaic)
- [ ] ExportStage

#### Pipeline Config

```yaml
# project.mapfree — pipeline config section
pipeline:
  quality: medium         # low | medium | high | ultra
  engine: colmap          # colmap | openmvg
  dense_engine: openmvs   # openmvs | colmap_mvs
  stages:
    - feature_extraction
    - matching
    - sparse_reconstruction
    - dense_reconstruction
    - geospatial
  options:
    feature_extraction:
      num_threads: 4
      use_gpu: true
    matching:
      method: exhaustive   # exhaustive | sequential | vocab_tree
```

- [ ] YAML-based pipeline config
- [ ] Per-stage config options
- [ ] Quality presets (low/medium/high/ultra)
- [ ] Pipeline validation sebelum run
- [ ] Resume dari stage manapun

---

### v1.4 — Logging System
*Target: Q3 2026*

**Focus: Logging yang jelas untuk pipeline photogrammetry**

```
Struktur log per job:
  logs/
  ├── pipeline.log              ← overall pipeline log
  ├── 01_feature_extraction.log ← per stage
  ├── 02_matching.log
  ├── 03_sparse_reconstruction.log
  │   ├── colmap_feature_extractor.stdout
  │   └── colmap_feature_extractor.stderr
  └── crash_report.txt          ← jika ada crash

Log format:
  [2026-03-06 10:30:15] [INFO] [FeatureExtraction] Starting...
  [2026-03-06 10:30:15] [INFO] [COLMAP] Running: colmap feature_extractor --image_path ...
  [2026-03-06 10:31:45] [INFO] [FeatureExtraction] Done. 335 images, 2.1M features. (90s)
  [2026-03-06 10:31:45] [ERROR] [Matching] COLMAP returned code 1
  [2026-03-06 10:31:45] [ERROR] [COLMAP] stderr: Out of memory
```

- [ ] `mapfree/logging/logger.py` — structured logger
- [ ] `mapfree/logging/handlers.py` — file + console + GUI handler
- [ ] Per-stage log file
- [ ] Crash report dengan stack trace + system info
- [ ] GUI: panel "Lihat Log" per stage
- [ ] Log viewer dengan filter level (INFO/WARNING/ERROR)
- [ ] Log retention: simpan N job terakhir, auto-delete yang lama

---

### v1.5 — GUI Architecture Overhaul
*Target: Q4 2026*

**Focus: GUI yang profesional dan sepenuhnya terpisah dari core**

#### API Bridge Pattern

```python
# mapfree/gui/api_bridge.py
# GUI HANYA berbicara melalui API Bridge

class MapFreeAPI(QObject):
    # Signals (core → GUI)
    progress_updated = Signal(float, str)   # percent, message
    stage_changed = Signal(str, str)        # stage_name, status
    job_finished = Signal(bool, str)        # success, message
    
    # Slots (GUI → core)
    @Slot(str, list)
    def start_reconstruction(self, project_path, image_paths):
        job = self._service.start(...)
        ...
    
    @Slot()
    def cancel_job(self):
        ...
```

#### GUI Components

```
main_window.py
├── Toolbar (Run, Stop, Load, Toggle View)
├── Left Panel (QSplitter-resizable, 260px default)
│   ├── DatasetPanel
│   │   ├── JobNameField
│   │   ├── PhotoListWidget  ← daftar foto + GPS status
│   │   ├── OutputPathWidget
│   │   └── QualitySelector
│   ├── OutputPanel
│   │   └── StageProgressList
│   └── MeasurementsPanel
└── Right Panel (expanding)
    ├── ViewerToolbar (3D | Map | Split)
    ├── ViewerStack
    │   ├── MapViewer (OSM basemap, GPS points)
    │   ├── PointCloudViewer (3D)
    │   └── MeshViewer (3D textured)
    └── StatusBar
        ├── ProjectLabel
        ├── StatusMessage
        └── SystemInfo (RAM | COLMAP ✓/✗)
```

- [ ] API Bridge selesai, GUI tidak import dari core langsung
- [ ] QSplitter responsive layout
- [ ] ViewerStack: toggle antara Map / 3D / Split
- [ ] Map viewer: OSM basemap + satellite toggle + auto-zoom
- [ ] Photo list: multi-select, GPS status per foto, drag-drop
- [ ] Pipeline progress: per-stage dengan ETA
- [ ] Log viewer terintegrasi
- [ ] Dark theme konsisten

---

### v1.6 — Plugin System
*Target: Q1 2027*

**Focus: MapFree sebagai framework riset photogrammetry**

```
mapfree/plugins/
├── base_plugin.py        ← AbstractPlugin interface
├── loader.py             ← discover & load plugins
└── builtin/
    ├── colmap_plugin.py
    └── openmvs_plugin.py

Plugin dapat berisi:
  - Custom Engine  (misal: PixSFM, HLoc, OpenMVG)
  - Custom Stage   (misal: ML-based matching, semantic segmentation)
  - Custom Algorithm (misal: custom bundle adjustment)
  - Custom Export  (misal: export ke format proprietary)

Plugin interface:
class AbstractPlugin:
  name: str
  version: str
  author: str
  
  def register_engines(self) -> list[AbstractEngine]
  def register_stages(self) -> list[BaseStage]
  def on_load(self) -> None
  def on_unload(self) -> None

Instalasi plugin:
  mapfree plugin install my_plugin.zip
  mapfree plugin list
  mapfree plugin enable my_plugin
```

**Plugin contoh yang bisa dibangun komunitas:**
- `mapfree-hloc` — HLoc (Hierarchical Localization) sebagai matching engine
- `mapfree-pixsfm` — PixSFM refinement stage
- `mapfree-instant-ngp` — NeRF export stage
- `mapfree-cloud` — Cloud processing integration

- [ ] AbstractPlugin interface
- [ ] Plugin loader (discovery via entry_points atau folder)
- [ ] Plugin manager CLI: `mapfree plugin install/list/enable/disable`
- [ ] Plugin manager GUI (Settings → Plugins)
- [ ] Dokumentasi: cara membuat plugin
- [ ] Contoh plugin: custom export (LAS, E57)

---

### v1.7 — Performance & Scale
*Target: Q2 2027*

**Focus: Dataset besar (500–5000 foto)**

- [ ] Async pipeline (asyncio + QThread) — GUI tidak freeze
- [ ] Multi-GPU support
- [ ] Memory monitoring + auto-tuning chunk size
- [ ] Tiled processing untuk area luas
- [ ] Progress ETA yang akurat
- [ ] Benchmark suite: 100 / 500 / 1000 / 5000 foto
- [ ] Cache hasil intermediate (skip re-run jika input sama)

---

## SUMMARY TIMELINE

| Version | Target | Focus |
|---------|--------|-------|
| v1.1.1 | Mar 2026 | Bug fix + UX (5 issues dari real-world test) |
| v1.1.0 | Mar 2026 | **RELEASE** — installer + smart setup |
| v1.2 | Q2 2026 | Core architecture refactor (Project, Job, Engine, Service) |
| v1.3 | Q3 2026 | Pipeline system upgrade (Stage system, config YAML) |
| v1.4 | Q3 2026 | Logging system (structured, per-stage) |
| v1.5 | Q4 2026 | GUI architecture overhaul (API Bridge, responsive) |
| v1.6 | Q1 2027 | Plugin system (framework riset) |
| v1.7 | Q2 2027 | Performance & Scale (500–5000 foto) |

---

## PRINSIP ARSITEKTUR

1. **Separation of Concerns** — GUI tidak tahu tentang COLMAP, Engine tidak tahu tentang GUI
2. **Dependency Inversion** — Pipeline bergantung ke AbstractEngine, bukan ColmapEngine langsung
3. **Testability** — Setiap layer dapat di-test tanpa layer lain (mock)
4. **Extensibility** — Tambah engine baru = implementasi AbstractEngine, tidak perlu ubah pipeline
5. **Fail-safe** — Setiap error di-log, pipeline bisa di-resume dari titik terakhir
6. **Developer-friendly** — Plugin system memungkinkan riset di atas MapFree tanpa fork

---

*MapFree Engine — Built for the field, designed for research.*
