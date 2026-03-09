"""Tests for mapfree.application.license_manager.

All tests mock MAPFREE_LICENSE_SECRET and ~/.mapfree/ paths so they don't
touch the user's real license cache or trial file.
"""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from mapfree.application.license_manager import (
    LicenseStatus,
    _decode_expiry,
    _get_trial_status,
    get_expiry_date,
    get_license_info,
    get_machine_id,
    is_feature_enabled,
    is_licensed,
    validate,
    validate_key,
)

_TEST_SECRET = "test-secret-key-for-unit-tests"


# ─── machine_id ──────────────────────────────────────────────────────────────


class TestGetMachineId:
    def test_returns_16_hex_chars(self):
        mid = get_machine_id()
        assert len(mid) == 16
        assert all(c in "0123456789abcdef" for c in mid)

    def test_stable_on_repeated_calls(self):
        assert get_machine_id() == get_machine_id()


# ─── validate ────────────────────────────────────────────────────────────────


# Key that we use with mock_hmac_for_valid_key: first 8 chars must match
# the value mock_hmac_for_valid_key returns for the message "deadbeef00000000:mid"
_VALID_KEY_FOR_MOCK = "DEAD-BEEF-0000-0000"


def _mock_hmac_for_valid_key(real_hmac):
    """Return a _compute_hmac replacement that accepts _VALID_KEY_FOR_MOCK."""
    def mock(secret: str, message: str) -> str:
        if "deadbeef00000000" in message.lower():
            return "deadbeef" + "0" * 56
        return real_hmac(secret, message)
    return mock


class TestValidate:
    def test_empty_key_returns_trial_status(self, tmp_path):
        with patch("mapfree.application.license_manager._TRIAL_FILE", tmp_path / "trial.json"):
            status = validate("")
            assert status in (LicenseStatus.TRIAL, LicenseStatus.TRIAL_EXPIRED)

    def test_invalid_format_returns_invalid(self):
        assert validate("NOT-A-VALID-KEY0") == LicenseStatus.INVALID

    def test_non_hex_chars_returns_invalid(self):
        assert validate("XXXX-XXXX-XXXX-XXXX") == LicenseStatus.INVALID

    def test_valid_key_returns_valid(self, tmp_path, monkeypatch):
        import mapfree.application.license_manager as lm
        monkeypatch.setenv("MAPFREE_LICENSE_SECRET", _TEST_SECRET)
        monkeypatch.setattr(lm, "_LICENSE_CACHE", tmp_path / "license.json")
        monkeypatch.setattr(lm, "_compute_hmac", _mock_hmac_for_valid_key(lm._compute_hmac))
        status = validate(_VALID_KEY_FOR_MOCK)
        assert status == LicenseStatus.VALID

    def test_valid_key_save_cache_failure_still_returns_valid(self, monkeypatch):
        """When _save_license_cache raises (e.g. disk full), validate still returns VALID."""
        from unittest.mock import MagicMock
        import mapfree.application.license_manager as lm
        monkeypatch.setenv("MAPFREE_LICENSE_SECRET", _TEST_SECRET)
        mock_cache = MagicMock()
        mock_cache.parent.mkdir = MagicMock()
        mock_cache.write_text.side_effect = OSError("Permission denied")
        monkeypatch.setattr(lm, "_LICENSE_CACHE", mock_cache)
        monkeypatch.setattr(lm, "_compute_hmac", _mock_hmac_for_valid_key(lm._compute_hmac))
        status = validate(_VALID_KEY_FOR_MOCK)
        assert status == LicenseStatus.VALID

    def test_wrong_key_returns_invalid(self, monkeypatch):
        monkeypatch.setenv("MAPFREE_LICENSE_SECRET", _TEST_SECRET)
        assert validate("AAAA-BBBB-CCCC-DDDD") == LicenseStatus.INVALID

    def test_cached_on_valid(self, tmp_path, monkeypatch):
        import mapfree.application.license_manager as lm
        monkeypatch.setenv("MAPFREE_LICENSE_SECRET", _TEST_SECRET)
        cache_file = tmp_path / "license.json"
        monkeypatch.setattr(lm, "_LICENSE_CACHE", cache_file)
        monkeypatch.setattr(lm, "_compute_hmac", _mock_hmac_for_valid_key(lm._compute_hmac))
        validate(_VALID_KEY_FOR_MOCK)
        assert cache_file.is_file()


# ─── decode_expiry ───────────────────────────────────────────────────────────


class TestDecodeExpiry:
    def test_zero_means_no_expiry(self):
        assert _decode_expiry("00000000") is None

    def test_future_date_decoded(self):
        # 1000 days since epoch 2020-01-01
        expiry = _decode_expiry(hex(1000)[2:].zfill(8))
        assert expiry is not None
        assert expiry.year > 2020

    def test_invalid_hex_returns_none(self):
        assert _decode_expiry("XXXXXXXX") is None


class TestGetExpiryDate:
    def test_key_length_not_16_returns_none(self):
        assert get_expiry_date("") is None
        assert get_expiry_date("DEAD") is None
        assert get_expiry_date("DEADBEEF00000000X") is None  # 17 chars
        assert get_expiry_date("DEAD-BEEF-0000-000") is None  # 15 hex chars


# ─── get_license_info (with cache) ────────────────────────────────────────────


class TestGetLicenseInfo:
    def test_with_cached_license_returns_status_and_expiry(self, tmp_path, monkeypatch):
        import mapfree.application.license_manager as lm
        monkeypatch.setattr(lm, "_LICENSE_CACHE", tmp_path / "license.json")
        cache_data = {
            "key": "DEAD-BEEF-0000-0000",
            "status": "valid",
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp_path.mkdir(parents=True, exist_ok=True)
        (tmp_path / "license.json").write_text(json.dumps(cache_data), encoding="utf-8")
        license_type, expiry = get_license_info()
        assert license_type == "valid"
        assert expiry is None or isinstance(expiry, str)

    def test_with_cached_license_with_expiry_date(self, tmp_path, monkeypatch):
        """Cache with key that encodes expiry hits get_expiry_date path."""
        import mapfree.application.license_manager as lm
        monkeypatch.setattr(lm, "_LICENSE_CACHE", tmp_path / "license.json")
        # Key suffix 00010000 = 65536 days since 2020-01-01 (future)
        cache_data = {
            "key": "DEADBEEF00010000",
            "status": "valid",
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp_path.mkdir(parents=True, exist_ok=True)
        (tmp_path / "license.json").write_text(json.dumps(cache_data), encoding="utf-8")
        license_type, expiry = get_license_info()
        assert license_type == "valid"
        assert expiry is not None and isinstance(expiry, str)
        assert len(expiry) == 10  # YYYY-MM-DD


class TestIsLicensed:
    def test_true_when_cached_valid(self, tmp_path, monkeypatch):
        import mapfree.application.license_manager as lm
        monkeypatch.setattr(lm, "_LICENSE_CACHE", tmp_path / "license.json")
        tmp_path.mkdir(parents=True, exist_ok=True)
        (tmp_path / "license.json").write_text(
            json.dumps({"key": "K", "status": "valid", "validated_at": "2026-01-01T00:00:00Z"}),
            encoding="utf-8",
        )
        assert is_licensed() is True


# ─── trial mode ──────────────────────────────────────────────────────────────


class TestTrialMode:
    def test_new_trial_file_created_on_first_launch(self, tmp_path):
        trial_file = tmp_path / "trial.json"
        with patch("mapfree.application.license_manager._TRIAL_FILE", trial_file):
            with patch("mapfree.application.license_manager._MAPFREE_DIR", tmp_path):
                status = _get_trial_status()
        assert status == LicenseStatus.TRIAL
        assert trial_file.is_file()

    def test_trial_active_within_30_days(self, tmp_path):
        trial_file = tmp_path / "trial.json"
        trial_file.write_text(
            json.dumps({"first_launch": datetime.now(timezone.utc).isoformat()})
        )
        with patch("mapfree.application.license_manager._TRIAL_FILE", trial_file):
            status = _get_trial_status()
        assert status == LicenseStatus.TRIAL

    def test_trial_expired_after_30_days(self, tmp_path):
        trial_file = tmp_path / "trial.json"
        past = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        trial_file.write_text(json.dumps({"first_launch": past}))
        with patch("mapfree.application.license_manager._TRIAL_FILE", trial_file):
            status = _get_trial_status()
        assert status == LicenseStatus.TRIAL_EXPIRED


# ─── is_feature_enabled ──────────────────────────────────────────────────────


class TestIsFeatureEnabled:
    def test_non_premium_always_true(self):
        assert is_feature_enabled("basic") is True
        assert is_feature_enabled("export") is True

    def test_premium_false_when_trial_expired(self, tmp_path):
        trial_file = tmp_path / "trial.json"
        past = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        trial_file.write_text(json.dumps({"first_launch": past}))
        with (
            patch("mapfree.application.license_manager._TRIAL_FILE", trial_file),
            patch("mapfree.application.license_manager._read_license_cache", return_value=None),
        ):
            assert is_feature_enabled("premium") is False


# ─── validate_key ────────────────────────────────────────────────────────────


class TestValidateKey:
    def test_invalid_key_returns_false_with_message(self):
        ok, msg = validate_key("INVALID-KEY-FORMAT-XX")
        assert ok is False
        assert isinstance(msg, str) and len(msg) > 0

    def test_valid_key_returns_true(self, tmp_path, monkeypatch):
        import mapfree.application.license_manager as lm
        monkeypatch.setenv("MAPFREE_LICENSE_SECRET", _TEST_SECRET)
        monkeypatch.setattr(lm, "_LICENSE_CACHE", tmp_path / "license.json")
        monkeypatch.setattr(lm, "_compute_hmac", _mock_hmac_for_valid_key(lm._compute_hmac))
        ok, msg = validate_key(_VALID_KEY_FOR_MOCK)
        assert ok is True
        assert "success" in msg.lower() or "valid" in msg.lower() or "activated" in msg.lower()

    def test_expired_key_returns_false_with_message(self, tmp_path, monkeypatch):
        """When key is valid but expiry is in the past, validate_key returns (False, expiry msg)."""
        import mapfree.application.license_manager as lm
        monkeypatch.setenv("MAPFREE_LICENSE_SECRET", _TEST_SECRET)
        monkeypatch.setattr(lm, "_LICENSE_CACHE", tmp_path / "license.json")
        orig_hmac = lm._compute_hmac
        monkeypatch.setattr(
            lm, "_compute_hmac",
            lambda s, m: "deadbeef" + "0" * 56 if "deadbeef00000001" in m.lower() else orig_hmac(s, m),
        )
        # Key with suffix 00000001 = 1 day since 2020-01-01 (past)
        ok, msg = validate_key("DEADBEEF00000001")
        assert ok is False
        assert "expired" in msg.lower()
