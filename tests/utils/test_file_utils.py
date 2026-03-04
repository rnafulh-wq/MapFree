"""Tests for mapfree.utils.file_utils."""
from pathlib import Path

from mapfree.utils.file_utils import ensure_dir, safe_remove, list_images


class TestEnsureDir:
    def test_creates_directory(self, tmp_path):
        d = tmp_path / "new_dir"
        result = ensure_dir(d)
        assert d.exists()
        assert result == d

    def test_creates_nested_dirs(self, tmp_path):
        d = tmp_path / "a" / "b" / "c"
        ensure_dir(d)
        assert d.exists()

    def test_idempotent_on_existing_dir(self, tmp_path):
        ensure_dir(tmp_path)  # already exists — no exception
        assert tmp_path.exists()


class TestSafeRemove:
    def test_removes_existing_file(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("data")
        result = safe_remove(f)
        assert result is True
        assert not f.exists()

    def test_returns_false_for_nonexistent(self, tmp_path):
        f = tmp_path / "missing.txt"
        result = safe_remove(f)
        assert result is False

    def test_returns_false_on_os_error(self, tmp_path, monkeypatch):
        f = tmp_path / "locked.txt"
        f.write_text("data")

        def raise_oserror(p):
            raise OSError("permission denied")

        monkeypatch.setattr(Path, "unlink", raise_oserror)
        result = safe_remove(f)
        assert result is False


class TestListImages:
    def test_returns_images(self, tmp_path):
        (tmp_path / "img1.jpg").write_bytes(b"")
        (tmp_path / "img2.png").write_bytes(b"")
        (tmp_path / "doc.txt").write_bytes(b"")
        images = list_images(tmp_path)
        names = [p.name for p in images]
        assert "img1.jpg" in names
        assert "img2.png" in names
        assert "doc.txt" not in names

    def test_sorted_result(self, tmp_path):
        for name in ["c.jpg", "a.jpg", "b.jpg"]:
            (tmp_path / name).write_bytes(b"")
        images = list_images(tmp_path)
        names = [p.name for p in images]
        assert names == sorted(names)

    def test_custom_extensions(self, tmp_path):
        (tmp_path / "model.ply").write_bytes(b"")
        (tmp_path / "img.jpg").write_bytes(b"")
        images = list_images(tmp_path, extensions=[".ply"])
        names = [p.name for p in images]
        assert "model.ply" in names
        assert "img.jpg" not in names

    def test_empty_directory(self, tmp_path):
        images = list_images(tmp_path)
        assert images == []
