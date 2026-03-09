"""
Minimal CRS handling for Stage 1. Projected CRS only; no external GIS library.
"""
from typing import Optional


class CRSManager:
    """
    Minimal CRS state and unit handling.
    Stage 1: assumes projected CRS only; unit is always meter.
    Extensible for future GIS integration.
    """

    def __init__(self, epsg_code: Optional[str] = None) -> None:
        """
        Initialize with optional EPSG code (e.g. "32632" for UTM 32N).

        Args:
            epsg_code: EPSG code as string, or None for unknown.
        """
        self._epsg = str(epsg_code).strip() if epsg_code else ""

    def set_crs(self, epsg_code: str) -> None:
        """Set the current CRS by EPSG code."""
        self._epsg = str(epsg_code).strip()

    def get_crs(self) -> str:
        """Return the current EPSG code, or empty string if not set."""
        return self._epsg

    def unit(self) -> str:
        """
        Return the linear unit for the current CRS.
        Stage 1: assume projected CRS only, so always "meter".
        """
        return "meter"

    def validate_projected(self) -> bool:
        """
        Check that the CRS is suitable for metric measurements (projected).
        Stage 1: no external GIS; returns True if any EPSG is set, else False.
        """
        return bool(self._epsg)
