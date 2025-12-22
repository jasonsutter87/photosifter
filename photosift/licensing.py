"""Licensing and freemium logic for PhotoSifter."""

import os
import json
import hashlib
import platform
from pathlib import Path
from datetime import datetime


FREE_TIER_LIMIT = 150  # Photos
APP_NAME = "PhotoSifter"


def get_app_data_dir() -> Path:
    """Get the appropriate app data directory for the current platform."""
    if platform.system() == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif platform.system() == "Darwin":  # macOS
        base = Path.home() / "Library" / "Application Support"
    else:  # Linux and others
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    app_dir = base / APP_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_machine_id() -> str:
    """Generate a unique machine identifier."""
    # Combine various system info for a stable machine ID
    info = f"{platform.node()}-{platform.machine()}-{platform.processor()}"
    return hashlib.sha256(info.encode()).hexdigest()[:32]


class LicenseManager:
    """Manages license state and validation."""

    def __init__(self):
        self.app_dir = get_app_data_dir()
        self.license_file = self.app_dir / "license.json"
        self.stats_file = self.app_dir / "stats.json"
        self._license_data: dict = {}
        self._stats: dict = {}
        self._load()

    def _load(self):
        """Load license and stats from disk."""
        if self.license_file.exists():
            try:
                self._license_data = json.loads(self.license_file.read_text())
            except Exception:
                self._license_data = {}

        if self.stats_file.exists():
            try:
                self._stats = json.loads(self.stats_file.read_text())
            except Exception:
                self._stats = {}

        # Initialize stats if needed
        if "photos_processed" not in self._stats:
            self._stats["photos_processed"] = 0
        if "first_run" not in self._stats:
            self._stats["first_run"] = datetime.now().isoformat()

    def _save(self):
        """Save license and stats to disk."""
        self.license_file.write_text(json.dumps(self._license_data, indent=2))
        self.stats_file.write_text(json.dumps(self._stats, indent=2))

    @property
    def is_licensed(self) -> bool:
        """Check if the app is licensed (paid version)."""
        if not self._license_data:
            return False

        license_key = self._license_data.get("license_key", "")
        machine_id = self._license_data.get("machine_id", "")

        # Verify license is for this machine
        if machine_id != get_machine_id():
            return False

        # Basic validation - in production, you'd verify with a server
        return self._validate_license_key(license_key)

    def _validate_license_key(self, key: str) -> bool:
        """
        Validate a license key.

        Accepts LemonSqueezy format: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
        (UUID-like format with alphanumeric characters)
        """
        if not key:
            return False

        # LemonSqueezy format: 8-4-4-4-12 (like UUID but alphanumeric)
        parts = key.split("-")
        if len(parts) != 5:
            return False

        expected_lengths = [8, 4, 4, 4, 12]
        for part, expected_len in zip(parts, expected_lengths):
            if len(part) != expected_len or not part.isalnum():
                return False

        return True

    @property
    def photos_processed(self) -> int:
        """Get total photos processed."""
        return self._stats.get("photos_processed", 0)

    @property
    def photos_remaining(self) -> int:
        """Get remaining photos in free tier."""
        if self.is_licensed:
            return float("inf")  # Unlimited
        return max(0, FREE_TIER_LIMIT - self.photos_processed)

    @property
    def is_free_tier_exhausted(self) -> bool:
        """Check if free tier limit is reached."""
        if self.is_licensed:
            return False
        return self.photos_processed >= FREE_TIER_LIMIT

    def can_process(self, count: int) -> tuple[bool, int]:
        """
        Check if we can process N photos.

        Returns: (can_process_all, max_allowed)
        """
        if self.is_licensed:
            return True, count

        remaining = self.photos_remaining
        if remaining >= count:
            return True, count
        elif remaining > 0:
            return False, remaining
        else:
            return False, 0

    def record_processed(self, count: int):
        """Record that N photos were processed."""
        self._stats["photos_processed"] = self.photos_processed + count
        self._stats["last_run"] = datetime.now().isoformat()
        self._save()

    def activate_license(self, license_key: str) -> tuple[bool, str]:
        """
        Attempt to activate a license key.

        Returns: (success, message)
        """
        if not self._validate_license_key(license_key):
            return False, "Invalid license key format"

        # In production, you'd verify with a license server here
        # For now, we just accept valid format keys

        self._license_data = {
            "license_key": license_key,
            "machine_id": get_machine_id(),
            "activated_at": datetime.now().isoformat(),
        }
        self._save()

        return True, "License activated successfully!"

    def deactivate_license(self):
        """Remove license from this machine."""
        self._license_data = {}
        self._save()

    def get_status_text(self) -> str:
        """Get human-readable license status."""
        if self.is_licensed:
            return "Licensed - Unlimited photos"
        else:
            remaining = self.photos_remaining
            return f"Free tier - {remaining:,} photos remaining"
