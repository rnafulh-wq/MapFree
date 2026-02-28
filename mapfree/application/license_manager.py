"""License validation and activation. Production stub."""

from typing import Optional, Tuple


def is_licensed() -> bool:
    """Return True if the application is licensed (e.g. valid key or trial)."""
    return True


def get_license_info() -> Tuple[Optional[str], Optional[str]]:
    """Return (license_type, expiry_or_none)."""
    return ("trial", None)


def validate_key(key: str) -> Tuple[bool, str]:
    """Validate an activation key. Return (success, message)."""
    return (False, "Not implemented")
