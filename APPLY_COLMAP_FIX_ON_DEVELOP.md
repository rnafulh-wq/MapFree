# Menerapkan perbaikan colmap_bin ke branch develop

Perbaikan colmap (binary dapat dikonfigurasi) ada di branch **fix/colmap-bin** di worktree ini.

Karena branch `develop` dipakai di worktree lain (`/media/pop_mangto/E/dev/MapFree`), lakukan salah satu:

## Opsi 1: Merge branch di repo utama

```bash
cd /media/pop_mangto/E/dev/MapFree
git fetch . /home/pop_mangto/.cursor/worktrees/MapFree/oka:fix/colmap-bin   # atau push fix/colmap-bin ke origin dulu
git checkout develop
git merge fix/colmap-bin -m "Merge fix/colmap-bin: configurable colmap binary"
# Tes ulang
```

Atau jika fix/colmap-bin sudah di-push ke origin:

```bash
cd /media/pop_mangto/E/dev/MapFree
git fetch origin
git checkout develop
git merge origin/fix/colmap-bin -m "Merge fix/colmap-bin: configurable colmap binary"
```

## Opsi 2: Apply patch di develop

```bash
cd /media/pop_mangto/E/dev/MapFree
git checkout develop
git apply /home/pop_mangto/.cursor/worktrees/MapFree/oka/colmap_bin_fix.patch
git add mapfree/config/default.yaml mapfree/core/chunking.py mapfree/engines/colmap_engine.py
git commit -m "fix: configurable colmap binary (MAPFREE_COLMAP_BIN / config colmap.colmap_bin)"
```

Lalu tes: `MAPFREE_COLMAP_BIN=/path/to/colmap mapfree run <images> -o <output>` atau set `colmap.colmap_bin` di config.
