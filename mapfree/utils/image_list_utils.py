"""Helpers for photo list: link (hardlink/symlink) or copy into project images folder."""

import os
import shutil
from pathlib import Path
from typing import List, Union


def _link_or_copy_one(src: Path, dest: Path) -> None:
    """
    Prefer hardlink (no extra disk), then symlink, then copy.
    Windows: hardlink works without admin; symlink often requires admin.
    If src and dest are the same file (e.g. re-run with images already in project),
    skip to avoid shutil.SameFileError.
    """
    src = src.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        try:
            if os.path.samefile(src, dest):
                return
        except OSError:
            pass
    try:
        os.link(src, dest)
        return
    except OSError:
        pass
    try:
        dest.symlink_to(src)
        return
    except OSError:
        pass
    shutil.copy2(src, dest)


def copy_or_link_images(
    source_paths: List[Union[Path, str]],
    dest_dir: Union[Path, str],
) -> None:
    """
    Link or copy image files into dest_dir so pipeline sees them in one folder.

    Prefers hardlink (all platforms), then symlink (Linux/macOS), then copy.
    Duplicate filenames are made unique by suffix (e.g. IMG_1.jpg, IMG_1_1.jpg).
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    seen_names: set[str] = set()
    for src in source_paths:
        src = Path(src)
        if not src.is_file():
            continue
        name = src.name
        if name in seen_names:
            stem, suf = src.stem, src.suffix
            n = 1
            while name in seen_names:
                name = f"{stem}_{n}{suf}"
                n += 1
        seen_names.add(name)
        dest = dest_dir / name
        _link_or_copy_one(src, dest)
