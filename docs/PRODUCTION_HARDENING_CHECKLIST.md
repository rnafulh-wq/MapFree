# Production Hardening Checklist

## 1️⃣ Engine Safety Layer (WAJIB)

### A. Subprocess Guard

Semua call ke:

- `colmap`
- `openmvs`
- external binary

Harus punya:

- Timeout support
- Exit code validation
- Retry (bounded)
- Log stdout + stderr
- Crash-safe abort

**Checklist:**

- [ ] wrapper.py untuk subprocess
- [ ] retry_count max 2
- [ ] timeout per stage configurable
- [ ] exception escalation ke pipeline
- [ ] log file per stage

---

## 2️⃣ Output Integrity Validation

Pastikan hasil bukan cuma folder ada.

- **Sparse valid** jika: `cameras.bin`, `images.bin`, `points3D.bin`
- **Dense valid** jika: `fused.ply` OR depth maps exist

**Checklist:**

- [ ] validate_sparse_model()
- [ ] validate_dense_model()
- [ ] validate_chunk_merge()

---

## 3️⃣ Logging Upgrade

Struktur logging production:

```
workspace/
 ├── logs/
 │   ├── run_20260216_001.log
 │   ├── hardware_snapshot.json
 │   ├── crash_report.json
```

**Checklist:**

- [ ] logging module terpisah
- [ ] structured JSON logging
- [ ] hardware snapshot saved
- [ ] full command log
- [ ] failure trace stored

---

## 4️⃣ State Locking

Tambahkan: **`.mapfree_lock`**

Agar:

- Tidak bisa run 2 pipeline di workspace sama
- Auto remove jika crash

**Checklist:**

- [ ] lock create
- [ ] lock release
- [ ] stale lock detect

---

## 5️⃣ Memory Guard

Sebelum run stage:

- cek free RAM
- cek VRAM
- fallback CPU jika VRAM < threshold

**Checklist:**

- [ ] safe memory threshold
- [ ] auto fallback GPU → CPU

---

## 6️⃣ Deterministic Build

**Checklist:**

- [ ] engine build script reproducible
- [ ] CUDA version pinned
- [ ] compiler version pinned
- [ ] build log saved
