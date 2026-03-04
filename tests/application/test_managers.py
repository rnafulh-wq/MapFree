"""Tests for mapfree.application.license_manager and project_manager."""
from mapfree.application.license_manager import is_licensed, get_license_info, validate_key
from mapfree.application.project_manager import open_project, save_project, recent_projects


class TestLicenseManager:
    def test_is_licensed_returns_bool(self):
        result = is_licensed()
        assert isinstance(result, bool)
        assert result is True  # stub returns True

    def test_get_license_info_returns_tuple(self):
        license_type, expiry = get_license_info()
        assert isinstance(license_type, (str, type(None)))

    def test_get_license_info_trial(self):
        license_type, expiry = get_license_info()
        assert license_type == "trial"
        assert expiry is None

    def test_validate_key_returns_tuple(self):
        result = validate_key("TEST-KEY-12345")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_validate_key_not_implemented(self):
        success, msg = validate_key("any-key")
        assert success is False
        assert isinstance(msg, str)


class TestProjectManager:
    def test_open_project_returns_none(self, tmp_path):
        result = open_project(tmp_path / "project.json")
        assert result is None

    def test_save_project_returns_bool(self, tmp_path):
        result = save_project(tmp_path / "project.json", {"name": "test"})
        assert isinstance(result, bool)

    def test_recent_projects_returns_list(self):
        result = recent_projects()
        assert isinstance(result, list)

    def test_recent_projects_max_count(self):
        result = recent_projects(max_count=5)
        assert isinstance(result, list)
        assert len(result) <= 5
