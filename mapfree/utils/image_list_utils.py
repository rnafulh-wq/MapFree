"""Helpers for photo list: copy/symlink into project images folder."""

import shutil
import sys
from pathlib import Path
from typing import List, Union


def copy_or_link_images(
    source_paths: List[Union[Path, str]],
    dest_dir: Union[Path, str],
) -> None:
    """
    Copy or link image files into dest_dir so pipeline sees them in one folder.

    On Windows we copy (symlink often requires admin). On Linux/macOS we use
    symlinks. Duplicate filenames are made unique by suffix (e.g. IMG_1.jpg, IMG_1_1.jpg).
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    seen_names: set[str] = set()
    use_symlink = sys.platform != "win32"
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
        try:
            if use_symlink:
                dest.symlink_to(src.resolve())
            else:
                shutil.copy2(src, dest)
        except OSError:
            shutil.copy2(src, dest)
