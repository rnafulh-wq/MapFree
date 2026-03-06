"""Tests for mapfree.core.project_structure."""

from pathlib import Path

from mapfree.core.project_structure import create_project_structure, resolve_project_paths


def test_creates_all_subfolders(tmp_path: Path) -> None:
    paths = create_project_structure(tmp_path, "demo")
    assert paths.root.is_dir()
    assert paths.images.is_dir()
    assert paths.sparse.is_dir()
    assert paths.dense.is_dir()
    assert paths.mesh.is_dir()
    assert paths.geospatial.is_dir()
    assert paths.exports.is_dir()
    assert paths.logs.is_dir()


def test_project_file_created(tmp_path: Path) -> None:
    paths = create_project_structure(tmp_path, "demo")
    assert paths.project_file.is_file()
    txt = paths.project_file.read_text(encoding="utf-8")
    assert "\"name\": \"demo\"" in txt


def test_idempotent_on_existing_project(tmp_path: Path) -> None:
    p1 = create_project_structure(tmp_path, "demo")
    mtime = p1.project_file.stat().st_mtime
    p2 = create_project_structure(tmp_path, "demo")
    assert p2.root == p1.root
    assert p2.project_file.stat().st_mtime == mtime


def test_paths_dict_has_all_keys(tmp_path: Path) -> None:
    paths = create_project_structure(tmp_path, "demo")
    d = paths.as_dict()
    for key in (
        "root",
        "project_file",
        "images",
        "sparse",
        "dense",
        "mesh",
        "geospatial",
        "exports",
        "logs",
    ):
        assert key in d


def test_resolve_project_paths_legacy(tmp_path: Path) -> None:
    root = tmp_path / "legacy"
    (root / "sparse").mkdir(parents=True)
    (root / "dense").mkdir(parents=True)
    (root / "geospatial").mkdir(parents=True)
    resolved = resolve_project_paths(root)
    assert resolved.sparse.name in ("sparse", "01_sparse")
    assert resolved.dense.name in ("dense", "02_dense")
    assert resolved.geospatial.name in ("geospatial", "04_geospatial")
