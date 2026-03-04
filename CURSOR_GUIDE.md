# MapFree — Cursor Quick Reference
# Cara menggunakan file-file ini di Cursor

---

## STRUKTUR FILE

```
.cursor/
└── rules/
    └── mapfree.mdc        ← Rules otomatis dibaca Cursor setiap saat

tasks/
├── fase1_stabilisasi.md   ← Sprint Maret: bug fix, CI/CD, testing
├── fase2_fitur.md         ← Sprint April: 3D viewer, lisensi, installer
└── fase3_produksi.md      ← Sprint Mei: packaging, QA, release v1.0
```

---

## CARA PAKAI DI CURSOR

### 1. Copy ke dalam repo MapFree
Taruh semua file ini di root repo:
```
MapFree/
├── .cursor/rules/mapfree.mdc
├── tasks/fase1_stabilisasi.md
├── tasks/fase2_fitur.md
└── tasks/fase3_produksi.md
```

### 2. Rules aktif otomatis
File `.cursor/rules/mapfree.mdc` akan otomatis dibaca Cursor
untuk setiap file Python, YAML, TOML, dan Shell yang kamu buka.
Tidak perlu setup tambahan.

### 3. Menjalankan task di Cursor Agent

**Cara paling efektif:**
Buka task file, copy blok "Cursor Prompt" dari task yang ingin dikerjakan,
lalu paste ke Cursor Agent (Cmd/Ctrl + L → Agent mode).

**Contoh untuk TASK 1.1:**
```
Buka tasks/fase1_stabilisasi.md, lihat TASK 1.1.
Copy prompt-nya → paste ke Cursor Agent → Enter.
```

**Prompt meta yang berguna:**
```
Baca tasks/fase1_stabilisasi.md dan kerjakan semua task yang masih [ ] (belum mulai),
mulai dari TASK 1.1. Setelah setiap task selesai, update status [ ] menjadi [x].
```

### 4. Update status task
Setelah task selesai, ubah manual di file:
```
- [ ] Item yang belum selesai
- [x] Item yang sudah selesai  
- [~] Item sedang dikerjakan
```

---

## PROMPT TEMPLATE SIAP PAKAI

### Mulai sesi kerja harian:
```
Baca tasks/fase1_stabilisasi.md (atau fase yang sedang berjalan).
Lihat item yang statusnya [ ] dan belum dikerjakan.
Kerjakan task berikutnya secara berurutan.
Ikuti semua rules di .cursor/rules/mapfree.mdc.
```

### Review kode yang sudah ditulis:
```
Review kode di [nama file] berdasarkan rules di .cursor/rules/mapfree.mdc.
Cek: type hints, docstrings, logging (tidak ada print), error handling,
dan layer boundary (core tidak import gui).
```

### Cek progress keseluruhan:
```
Baca tasks/fase1_stabilisasi.md, fase2_fitur.md, dan fase3_produksi.md.
Buat ringkasan: berapa task yang sudah [x], berapa [~], berapa [ ].
Hitung persentase completion per fase.
```

### Sebelum commit:
```
Sebelum commit, pastikan:
1. flake8 mapfree/ tests/ tidak ada error
2. pytest tests/ semua hijau  
3. Tidak ada file .mapfree_state.json atau *.log yang ter-stage
4. Commit message format: <type>(<scope>): <pesan>
```

---

## URUTAN PENGERJAAN YANG DISARANKAN

Fase 1 (Maret) — kerjakan berurutan:
1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6 → 1.7 → 1.8 → 1.9 → 1.10 → 1.11

Fase 2 (April) — bisa paralel dalam sprint:
Sprint 2A: 2.1 + 2.2 (viewer, bisa paralel)
Sprint 2B: 2.3 → 2.4 → 2.5 (lisensi, berurutan)
Sprint 2C: 2.6 + 2.7 + 2.8 (bisa paralel)

Fase 3 (Mei) — berurutan:
3.1 → 3.2 → 3.3 (build dulu) → 3.4 + 3.5 + 3.6 (paralel) → 3.7 → 3.8 (terakhir)
```
