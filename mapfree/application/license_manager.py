"""Offline license validation with HMAC-SHA256.

License key format: ``XXXX-XXXX-XXXX-XXXX`` (16 hex characters, dash-separated).

Validation flow:

1. Strip dashes → 16-char hex string.
2. Derive HMAC-SHA256(secret, ``f"{key}:{machine_id}"``).
3. If the first 8 hex chars of the HMAC match the first 8 chars of the key
   → VALID.  This is a simple demo scheme; replace with your own protocol.

Trial mode:

* On first launch without a key, ``~/.mapfree/trial.json`` is created with
  ``{"first_launch": "<ISO date>"}`` .
* Trial is active for 30 days after ``first_launch``.
* After trial expiry ``is_feature_enabled("premium")`` returns ``False``.

Environment variables:

* ``MAPFREE_LICENSE_SECRET`` — HMAC secret key.  Defaults to
  ``"mapfree-dev-secret-2024"`` for development.
"""
import hashlib
import hmac
import json
import logging
import os
import platform
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("mapfree.license_manager")

_MAPFREE_DIR = Path.home() / ".mapfree"
_LICENSE_CACHE = _MAPFREE_DIR / "license.json"
_TRIAL_FILE = _MAPFREE_DIR / "trial.json"
_TRIAL_DAYS = 30
_DEFAULT_SECRET = "mapfree-dev-secret-2024"
_KEY_PATTERN_LEN = 19  # "XXXX-XXXX-XXXX-XXXX"


class LicenseStatus(str, Enum):
    """Possible license states."""

    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"
    TRIAL = "trial"
    TRIAL_EXPIRED = "trial_expired"


__all__ = [
    "LicenseStatus",
    "get_machine_id",
    "validate",
    "get_expiry_date",
    "is_feature_enabled",
    "get_license_info",
    "is_licensed",
    "validate_key",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_machine_id() -> str:
    """Return a stable, anonymised machine identifier.

    Derived from the MAC address and CPU info via SHA-256.  The result is
    the first 16 hex characters of the hash — stable across restarts but
    not directly reversible to hardware identifiers.

    Returns:
        16-character hex string, e.g. ``"a1b2c3d4e5f60718"``.
    """
    raw = _get_raw_machine_string()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def validate(key: str) -> LicenseStatus:
    """Validate a license key.

    Args:
        key: License key in ``XXXX-XXXX-XXXX-XXXX`` format (case-insensitive).

    Returns:
        A :class:`LicenseStatus` value.
    """
    key = key.strip().upper()
    if not key:
        return _get_trial_status()

    clean = key.replace("-", "")
    if len(clean) != 16 or not _is_hex(clean):
        return LicenseStatus.INVALID

    machine_id = get_machine_id()
    secret = os.environ.get("MAPFREE_LICENSE_SECRET", _DEFAULT_SECRET)
    expected_hmac = _compute_hmac(secret, f"{clean}:{machine_id}")

    # Simple check: first 8 chars of key must match first 8 chars of HMAC
    if clean[:8].lower() == expected_hmac[:8].lower():
        # Check for expiry encoded in key (chars 8-16)
        expiry = _decode_expiry(clean[8:])
        if expiry is not None and datetime.now(timezone.utc) > expiry:
            status = LicenseStatus.EXPIRED
        else:
            status = LicenseStatus.VALID
        _save_license_cache(key, status)
        return status

    return LicenseStatus.INVALID


def get_expiry_date(key: str) -> Optional[datetime]:
    """Return the expiry date encoded in a license key, or ``None``.

    Args:
        key: License key string.

    Returns:
        :class:`datetime` (UTC, timezone-aware) or ``None`` if the key has
        no expiry or is invalid.
    """
    clean = key.strip().upper().replace("-", "")
    if len(clean) != 16:
        return None
    return _decode_expiry(clean[8:])


def is_feature_enabled(feature: str) -> bool:
    """Return whether *feature* is enabled under the current license.

    Premium features are gated behind a valid or active-trial license.
    Core features are always enabled.

    Args:
        feature: Feature identifier string, e.g. ``"premium"``.

    Returns:
        ``True`` if the feature is accessible.
    """
    if feature == "premium":
        status = _load_cached_status()
        if status in (LicenseStatus.VALID,):
            return True
        trial = _get_trial_status()
        return trial == LicenseStatus.TRIAL
    # All non-premium features are always enabled
    return True


def get_license_info() -> Tuple[str, Optional[str]]:
    """Return ``(license_type, expiry_or_none)`` for display.

    Returns:
        Tuple of ``(type_string, expiry_string_or_None)``.
        ``type_string`` is one of ``"valid"``, ``"trial"``, ``"trial_expired"``,
        ``"invalid"``, ``"expired"``, or ``"none"``.
    """
    cache = _read_license_cache()
    if cache:
        key = cache.get("key", "")
        status_str = cache.get("status", "")
        expiry = get_expiry_date(key) if key else None
        expiry_str = expiry.strftime("%Y-%m-%d") if expiry else None
        return status_str or "unknown", expiry_str

    trial = _get_trial_status()
    if trial == LicenseStatus.TRIAL:
        remaining = _trial_days_remaining()
        return "trial", f"{remaining} days remaining"
    if trial == LicenseStatus.TRIAL_EXPIRED:
        return "trial_expired", None
    return "none", None


def is_licensed() -> bool:
    """Return ``True`` if the application has a valid license or active trial."""
    status = _load_cached_status()
    if status == LicenseStatus.VALID:
        return True
    return _get_trial_status() == LicenseStatus.TRIAL


def validate_key(key: str) -> Tuple[bool, str]:
    """Validate key and return ``(success, human_readable_message)``."""
    status = validate(key)
    messages = {
        LicenseStatus.VALID: "License activated successfully.",
        LicenseStatus.EXPIRED: "License key has expired.",
        LicenseStatus.INVALID: "Invalid license key.",
        LicenseStatus.TRIAL: "Trial mode active.",
        LicenseStatus.TRIAL_EXPIRED: "Trial period has expired.",
    }
    return status == LicenseStatus.VALID, messages.get(status, "Unknown status.")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _get_raw_machine_string() -> str:
    """Build a stable string representing this machine."""
    parts = []
    # MAC address of the primary interface (uuid.getnode() returns 48-bit int)
    mac = uuid.getnode()
    parts.append(hex(mac))
    # CPU / platform info
    parts.append(platform.processor() or platform.machine() or "unknown")
    parts.append(platform.node() or "unknown")
    return "|".join(parts)


def _is_hex(s: str) -> bool:
    try:
        int(s, 16)
        return True
    except ValueError:
        return False


def _compute_hmac(secret: str, message: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _decode_expiry(chars_8: str) -> Optional[datetime]:
    """Decode 8-char hex suffix as days-since-epoch expiry (0 = no expiry)."""
    try:
        days = int(chars_8, 16)
        if days == 0:
            return None
        epoch = datetime(2020, 1, 1, tzinfo=timezone.utc)
        return epoch + timedelta(days=days)
    except (ValueError, OverflowError):
        return None


def _save_license_cache(key: str, status: LicenseStatus) -> None:
    try:
        _MAPFREE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "key": key,
            "status": status.value,
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }
        _LICENSE_CACHE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not save license cache: %s", exc)


def _read_license_cache() -> Optional[dict]:
    try:
        if _LICENSE_CACHE.is_file():
            return json.loads(_LICENSE_CACHE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _load_cached_status() -> Optional[LicenseStatus]:
    cache = _read_license_cache()
    if cache:
        try:
            return LicenseStatus(cache.get("status", ""))
        except ValueError:
            pass
    return None


def _get_trial_status() -> LicenseStatus:
    """Return TRIAL, TRIAL_EXPIRED, or INVALID based on ~/.mapfree/trial.json."""
    try:
        _MAPFREE_DIR.mkdir(parents=True, exist_ok=True)
        if not _TRIAL_FILE.is_file():
            data = {"first_launch": datetime.now(timezone.utc).isoformat()}
            _TRIAL_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return LicenseStatus.TRIAL

        raw = json.loads(_TRIAL_FILE.read_text(encoding="utf-8"))
        first = datetime.fromisoformat(raw.get("first_launch", ""))
        if first.tzinfo is None:
            first = first.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) <= first + timedelta(days=_TRIAL_DAYS):
            return LicenseStatus.TRIAL
        return LicenseStatus.TRIAL_EXPIRED
    except Exception as exc:
        logger.debug("Trial check failed: %s", exc)
        return LicenseStatus.TRIAL


def _trial_days_remaining() -> int:
    """Return the number of trial days remaining (0 if expired)."""
    try:
        raw = json.loads(_TRIAL_FILE.read_text(encoding="utf-8"))
        first = datetime.fromisoformat(raw.get("first_launch", ""))
        if first.tzinfo is None:
            first = first.replace(tzinfo=timezone.utc)
        expiry = first + timedelta(days=_TRIAL_DAYS)
        remaining = (expiry - datetime.now(timezone.utc)).days
        return max(0, remaining)
    except Exception:
        return 0
