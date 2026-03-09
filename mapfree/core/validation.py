"""
Validation of engine outputs (sparse/dense dirs) and user input paths.
State does not know engine output layout; this module does.
"""
import os
import sys
from pathlib import Path

from mapfree.core.exceptions import ProjectValidationError

# System directories that must not be used as project/image paths
_FORBIDDEN_SYSTEM_ROOTS = ()  # set per platform below
if sys.platform == "win32":
    _FORBIDDEN_SYSTEM_ROOTS = frozenset(
        Path(p).resolve() for p in (
            os.environ.get("SystemRoot", "C:\\Windows") + "\\System32",
            os.environ.get("SystemRoot", "C:\\Windows") + "\\SysWOW64",
        )
    )
else:
    _FORBIDDEN_SYSTEM_ROOTS = frozenset(
        Path(p) for p in ("/etc", "/sys", "/proc", "/dev", "/bin", "/sbin", "/usr/bin")
    )


def file_valid(path) -> bool:
    """File exists and has size > 0."""
    p = Path(path)
    return p.is_file() and p.stat().st_size > 0


def sparse_valid(sparse_dir) -> bool:
    """Sparse dir (e.g. .../sparse_merged/0 or .../sparse/0) has cameras.bin and non-empty images/points3D."""
    d = Path(sparse_dir)
    cam = d / "cameras.bin"
    if not file_valid(cam):
        return False
    for name in ("images.bin", "points3D.bin"):
        f = d / name
        if f.exists() and f.stat().st_size == 0:
            return False
    return True


def dense_valid(dense_path) -> bool:
    """Dense folder has fused.ply (size > 0) and is non-empty."""
    d = Path(dense_path)
    fused = d / "fused.ply"
    if not file_valid(fused):
        return False
    try:
        return any(d.iterdir())
    except OSError:
        return False


def validate_path_allowed(
    path: str | Path,
    allowed_base: str | Path | None = None,
    kind: str = "path",
) -> Path:
    """
    Validate path for use as project or image directory. No allowed_base restriction;
    path must be absolute, must not be a forbidden system directory, and parent must be writable.

    - Path is resolved; must be absolute (no relative that escapes).
    - Path must not contain traversal that resolves into forbidden system dirs.
    - Path must not be under Windows System32/SysWOW64 or Linux /etc, /sys, /proc, etc.
    - Parent directory must exist and be writable (path must be creatable).

    Raises ProjectValidationError if validation fails.
    Returns resolved Path. allowed_base is ignored (kept for API compatibility).
    """
    resolved = Path(path).resolve()
    if not resolved.is_absolute():
        raise ProjectValidationError(
            "Path tidak diizinkan: %s harus path absolut." % kind
        )

    # Reject if path is inside or equals a forbidden system root
    try:
        for forbidden in _FORBIDDEN_SYSTEM_ROOTS:
            f = forbidden.resolve()
            try:
                resolved.relative_to(f)
                raise ProjectValidationError(
                    "Path tidak diizinkan: %s tidak boleh di dalam direktori sistem (%s)."
                    % (kind, f)
                ) from None
            except ValueError:
                pass
    except ProjectValidationError:
        raise
    except Exception:
        pass

    # Parent must exist and be writable so the path can be created
    parent = resolved.parent
    if not parent.exists():
        raise ProjectValidationError(
            "Path tidak diizinkan: direktori induk tidak ada (%s)." % parent
        )
    if not os.access(str(parent), os.W_OK):
        raise ProjectValidationError(
            "Path tidak diizinkan: direktori induk tidak dapat ditulis (%s)." % parent
        )
    return resolved
