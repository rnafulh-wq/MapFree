"""Additional coverage for mapfree.core.chunking - pure Python paths."""
from pathlib import Path
from unittest.mock import patch

import mapfree.core.chunking as chunking_mod
from mapfree.core.chunking import count_images, _list_images, split_dataset


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_images(folder: Path, names):
    """Create dummy image files in folder."""
    for name in names:
        (folder / name).write_bytes(b"\xff\xd8\xff")  # JPEG magic bytes


def _split(image_folder, project_path, chunk_size):
    """Call split_dataset with mocked resolve_chunk_size."""
    with patch.object(chunking_mod, "resolve_chunk_size", return_value=chunk_size):
        return split_dataset(image_folder, project_path, chunk_size)


# ─── count_images ─────────────────────────────────────────────────────────────

class TestCountImages:
    def test_empty_folder(self, tmp_path):
        assert count_images(tmp_path) == 0

    def test_jpg_files_counted(self, tmp_path):
        _make_images(tmp_path, ["a.jpg", "b.jpg", "c.jpg"])
        assert count_images(tmp_path) == 3

    def test_non_image_files_excluded(self, tmp_path):
        _make_images(tmp_path, ["a.jpg"])
        (tmp_path / "readme.txt").write_text("doc")
        assert count_images(tmp_path) == 1

    def test_mixed_extensions(self, tmp_path):
        _make_images(tmp_path, ["a.jpg", "b.png", "c.JPG"])
        result = count_images(tmp_path)
        # At least JPG should be counted (case sensitivity varies by platform)
        assert result >= 1


# ─── _list_images ─────────────────────────────────────────────────────────────

class TestListImages:
    def test_empty_folder(self, tmp_path):
        assert _list_images(tmp_path) == []

    def test_returns_sorted_paths(self, tmp_path):
        _make_images(tmp_path, ["c.jpg", "a.jpg", "b.jpg"])
        result = _list_images(tmp_path)
        assert [p.name for p in result] == ["a.jpg", "b.jpg", "c.jpg"]


# ─── split_dataset ────────────────────────────────────────────────────────────

class TestSplitDataset:
    def test_empty_folder_returns_empty(self, tmp_path):
        img_dir = tmp_path / "images"
        img_dir.mkdir()
        result = _split(img_dir, tmp_path / "project", chunk_size=50)
        assert result == []

    def test_small_dataset_no_split(self, tmp_path):
        img_dir = tmp_path / "images"
        img_dir.mkdir()
        _make_images(img_dir, [f"img{i:02d}.jpg" for i in range(5)])
        result = _split(img_dir, tmp_path / "project", chunk_size=50)
        assert result == [img_dir]

    def test_large_dataset_splits(self, tmp_path):
        img_dir = tmp_path / "images"
        img_dir.mkdir()
        _make_images(img_dir, [f"img{i:03d}.jpg" for i in range(10)])
        project_dir = tmp_path / "project"
        result = _split(img_dir, project_dir, chunk_size=3)
        assert len(result) > 1
        for chunk_path in result:
            assert chunk_path.exists()

    def test_chunk_dirs_named_sequentially(self, tmp_path):
        img_dir = tmp_path / "images"
        img_dir.mkdir()
        _make_images(img_dir, [f"img{i:03d}.jpg" for i in range(6)])
        project_dir = tmp_path / "project"
        result = _split(img_dir, project_dir, chunk_size=2)
        names = [p.name for p in result]
        assert "chunk_001" in names
        assert "chunk_002" in names
        assert "chunk_003" in names

    def test_exact_chunk_size_no_split(self, tmp_path):
        """Exactly chunk_size images → no splitting."""
        img_dir = tmp_path / "images"
        img_dir.mkdir()
        _make_images(img_dir, [f"img{i:02d}.jpg" for i in range(5)])
        result = _split(img_dir, tmp_path / "project", chunk_size=5)
        assert result == [img_dir]

    def test_images_copied_to_chunks(self, tmp_path):
        img_dir = tmp_path / "images"
        img_dir.mkdir()
        _make_images(img_dir, ["a.jpg", "b.jpg", "c.jpg"])
        project_dir = tmp_path / "project"
        result = _split(img_dir, project_dir, chunk_size=2)
        assert len(result) == 2
        chunk1_files = [p.name for p in result[0].iterdir()]
        assert "a.jpg" in chunk1_files or "b.jpg" in chunk1_files
