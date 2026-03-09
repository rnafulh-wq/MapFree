"""Settings tab — GCP and Camera Calibration placeholders for v1.2."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QGroupBox,
    QFormLayout,
)


class SettingsPlaceholderPanel(QWidget):
    """Settings tab: GCP and Camera Calibration (placeholders for v1.2)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        gcp_grp = QGroupBox("Ground Control Points (GCP)")
        gcp_grp.setObjectName("settingsGroup")
        fl1 = QFormLayout(gcp_grp)
        fl1.addRow(QLabel("Coming in v1.2 — import GCP file and assign to photos."))
        layout.addWidget(gcp_grp)

        cam_grp = QGroupBox("Camera Calibration")
        cam_grp.setObjectName("settingsGroup")
        fl2 = QFormLayout(cam_grp)
        fl2.addRow(QLabel("Coming in v1.2 — custom camera parameters and lens model."))
        layout.addWidget(cam_grp)

        layout.addStretch()
