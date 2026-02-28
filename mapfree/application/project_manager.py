"""Project open/save, recent list, validation. Production stub."""

from pathlib import Path
from typing import List, Optional


def open_project(path: Path) -> Optional[dict]:
    """Load project from path. Return project dict or None on error."""
    return None


def save_project(path: Path, data: dict) -> bool:
    """Save project to path. Return True on success."""
    return False


def recent_projects(max_count: int = 10) -> List[Path]:
    """Return list of recent project paths."""
    return []
