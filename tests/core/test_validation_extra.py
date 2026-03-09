"""Extra tests for mapfree.core.validation (dense_valid, edge cases)."""
from mapfree.core.validation import file_valid, sparse_valid, dense_valid


class TestFileValid:
    def test_nonexistent_file(self, tmp_path):
        assert file_valid(tmp_path / "missing.bin") is False

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        assert file_valid(f) is False

    def test_nonempty_file(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_bytes(b"data")
        assert file_valid(f) is True

    def test_directory_not_file(self, tmp_path):
        assert file_valid(tmp_path) is False


class TestDenseValid:
    def test_no_fused_ply(self, tmp_path):
        assert dense_valid(tmp_path) is False

    def test_empty_fused_ply(self, tmp_path):
        (tmp_path / "fused.ply").write_bytes(b"")
        assert dense_valid(tmp_path) is False

    def test_valid_dense(self, tmp_path):
        (tmp_path / "fused.ply").write_bytes(b"ply header data")
        (tmp_path / "extra.txt").write_bytes(b"data")
        assert dense_valid(tmp_path) is True

    def test_fused_ply_only_entry(self, tmp_path):
        """Dense dir with only fused.ply → iterdir finds at least 1 item → valid."""
        (tmp_path / "fused.ply").write_bytes(b"ply data")
        assert dense_valid(tmp_path) is True


class TestSparseValidExtra:
    def test_empty_images_bin_invalid(self, tmp_path):
        (tmp_path / "cameras.bin").write_bytes(b"cams")
        (tmp_path / "images.bin").write_bytes(b"")  # empty
        (tmp_path / "points3D.bin").write_bytes(b"pts")
        assert sparse_valid(tmp_path) is False

    def test_empty_points3d_invalid(self, tmp_path):
        (tmp_path / "cameras.bin").write_bytes(b"cams")
        (tmp_path / "images.bin").write_bytes(b"imgs")
        (tmp_path / "points3D.bin").write_bytes(b"")
        assert sparse_valid(tmp_path) is False

    def test_valid_sparse(self, tmp_path):
        (tmp_path / "cameras.bin").write_bytes(b"cams")
        (tmp_path / "images.bin").write_bytes(b"imgs")
        (tmp_path / "points3D.bin").write_bytes(b"pts")
        assert sparse_valid(tmp_path) is True
