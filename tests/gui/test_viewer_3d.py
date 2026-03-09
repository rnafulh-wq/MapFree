"""GUI tests for mapfree.gui.panels.viewer_3d and viewer_panel.

Requires PySide6.  Skipped automatically in environments where PySide6 is
not installed.

PLY parser unit tests (no Qt dependency) live in tests/utils/test_ply_parser.py.
"""
from pathlib import Path

import numpy as np
import pytest

# Skip the whole module when PySide6 is not installed (e.g. minimal CI envs)
pytest.importorskip("PySide6", reason="PySide6 not installed — skipping GUI tests")


# ─── PLY helpers (duplicated from test_ply_parser for local fixture use) ─────


def _write_ascii_ply(path: Path, xyz: np.ndarray, rgb: np.ndarray | None = None) -> None:
    has_color = rgb is not None
    props = ["property float x", "property float y", "property float z"]
    if has_color:
        props += ["property uchar red", "property uchar green", "property uchar blue"]
    header = "\n".join(
        ["ply", "format ascii 1.0", f"element vertex {len(xyz)}", *props, "end_header"]
    ) + "\n"
    with open(path, "w") as fh:
        fh.write(header)
        for i, (x, y, z) in enumerate(xyz):
            if has_color:
                r, g, b = rgb[i]
                fh.write(f"{x} {y} {z} {int(r)} {int(g)} {int(b)}\n")
            else:
                fh.write(f"{x} {y} {z}\n")


# ─── PointCloudViewer widget tests ───────────────────────────────────────────


@pytest.mark.gui
class TestPointCloudViewer:
    """Tests for PointCloudViewer in fallback mode (MAPFREE_NO_OPENGL=1)."""

    def test_construction_no_crash(self, qapp):
        """Widget can be constructed without a display / OpenGL context."""
        from mapfree.gui.panels.viewer_3d import PointCloudViewer
        viewer = PointCloudViewer()
        assert viewer is not None

    def test_initial_point_count_is_zero(self, qapp):
        """Fresh viewer reports 0 points."""
        from mapfree.gui.panels.viewer_3d import PointCloudViewer
        assert PointCloudViewer().point_count() == 0

    def test_load_ply_valid(self, qapp, tmp_path):
        """load_ply with a valid 3-point PLY never crashes; count correct when GL available."""
        from mapfree.gui.panels.viewer_3d import PointCloudViewer

        xyz = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [2.0, 2.0, 2.0]], dtype=np.float32)
        ply = tmp_path / "test.ply"
        _write_ascii_ply(ply, xyz)

        viewer = PointCloudViewer()
        loaded_counts: list[int] = []
        viewer.pointsLoaded.connect(loaded_counts.append)

        result = viewer.load_ply(str(ply))

        # With GL: True and correct count; without GL: False but no crash.
        assert isinstance(result, bool)
        if result:
            assert viewer.point_count() == 3
            assert loaded_counts == [3]

    def test_load_ply_missing_file(self, qapp):
        """load_ply with non-existent path → False, loadError emitted."""
        from mapfree.gui.panels.viewer_3d import PointCloudViewer

        viewer = PointCloudViewer()
        errors: list[str] = []
        viewer.loadError.connect(errors.append)

        result = viewer.load_ply("/nonexistent/path/file.ply")

        assert result is False
        assert len(errors) == 1

    def test_load_ply_corrupt_file(self, qapp, tmp_path):
        """load_ply with corrupt file → False, no crash."""
        from mapfree.gui.panels.viewer_3d import PointCloudViewer

        bad = tmp_path / "bad.ply"
        bad.write_bytes(b"garbage data\xff\x00")

        result = PointCloudViewer().load_ply(str(bad))
        assert result is False

    def test_refresh_points_nx6_updates_state(self, qapp):
        """refresh_points with Nx6 float array sets point_count to N."""
        from mapfree.gui.panels.viewer_3d import PointCloudViewer

        viewer = PointCloudViewer()
        data = np.random.default_rng(0).random((100, 6)).astype(np.float32)
        viewer.refresh_points(data)
        assert viewer.point_count() == 100

    def test_refresh_points_nx3_no_crash(self, qapp):
        """refresh_points with Nx3 (xyz only) does not crash."""
        from mapfree.gui.panels.viewer_3d import PointCloudViewer

        viewer = PointCloudViewer()
        viewer.refresh_points(np.ones((50, 3), dtype=np.float32))
        assert viewer.point_count() == 50

    def test_refresh_points_invalid_shape_no_crash(self, qapp):
        """refresh_points with wrong shape (Nx2) does not crash, count stays 0."""
        from mapfree.gui.panels.viewer_3d import PointCloudViewer

        viewer = PointCloudViewer()
        viewer.refresh_points(np.zeros((10, 2), dtype=np.float32))
        assert viewer.point_count() == 0

    def test_clear_resets_count(self, qapp, tmp_path):
        """clear() resets point_count to 0."""
        from mapfree.gui.panels.viewer_3d import PointCloudViewer

        xyz = np.ones((5, 3), dtype=np.float32)
        ply = tmp_path / "c.ply"
        _write_ascii_ply(ply, xyz)

        viewer = PointCloudViewer()
        viewer.load_ply(str(ply))
        viewer.clear()
        assert viewer.point_count() == 0

    def test_viewer_no_opengl_shows_placeholder(self, qapp, monkeypatch):
        """With pyqtgraph unavailable the GL view is not created."""
        import mapfree.gui.panels.viewer_3d as _mod

        original = _mod._PYQTGRAPH_AVAILABLE
        monkeypatch.setattr(_mod, "_PYQTGRAPH_AVAILABLE", False)
        try:
            viewer = _mod.PointCloudViewer()
            assert viewer._gl_view is None
        finally:
            monkeypatch.setattr(_mod, "_PYQTGRAPH_AVAILABLE", original)


# ─── ViewerPanel integration tests ───────────────────────────────────────────


@pytest.mark.gui
class TestViewerPanel:
    """Integration tests for the upgraded ViewerPanel."""

    def test_construction_no_crash(self, qapp):
        from mapfree.gui.panels.viewer_panel import ViewerPanel
        assert ViewerPanel() is not None

    def test_get_visualizer_returns_pc_viewer(self, qapp):
        from mapfree.gui.panels.viewer_panel import ViewerPanel
        from mapfree.gui.panels.viewer_3d import PointCloudViewer

        panel = ViewerPanel()
        assert isinstance(panel.get_visualizer(), PointCloudViewer)

    def test_load_point_cloud_missing_file(self, qapp):
        from mapfree.gui.panels.viewer_panel import ViewerPanel

        assert ViewerPanel().load_point_cloud("/no/such/file.ply") is False

    def test_load_point_cloud_valid_no_crash(self, qapp, tmp_path):
        """load_point_cloud with valid PLY never crashes (returns bool)."""
        from mapfree.gui.panels.viewer_panel import ViewerPanel

        xyz = np.ones((4, 3), dtype=np.float32)
        ply = tmp_path / "valid.ply"
        _write_ascii_ply(ply, xyz)

        assert isinstance(ViewerPanel().load_point_cloud(str(ply)), bool)

    def test_load_raster_missing(self, qapp):
        from mapfree.gui.panels.viewer_panel import ViewerPanel

        assert ViewerPanel().load_raster("/missing/image.png") is False

    def test_load_raster_valid(self, qapp, tmp_path):
        """load_raster with a real image file returns True."""
        from PySide6.QtGui import QColor, QImage
        from mapfree.gui.panels.viewer_panel import ViewerPanel

        img = QImage(10, 10, QImage.Format.Format_RGB32)
        img.fill(QColor(100, 150, 200))
        img_path = str(tmp_path / "test.png")
        img.save(img_path)

        assert ViewerPanel().load_raster(img_path) is True

    def test_clear_scene_no_crash(self, qapp, tmp_path):
        """clear_scene() does not crash and resets point count."""
        from mapfree.gui.panels.viewer_panel import ViewerPanel

        xyz = np.ones((3, 3), dtype=np.float32)
        ply = tmp_path / "t.ply"
        _write_ascii_ply(ply, xyz)

        panel = ViewerPanel()
        panel.load_point_cloud(str(ply))
        panel.clear_scene()
        assert panel.get_visualizer().point_count() == 0
