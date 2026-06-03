"""Manifest repository for dev copy lifecycle tracking.

Tracks the relationship between production and development
database copies so we can deploy or discard changes safely.
"""

import hashlib
import json
import os
import tempfile
from typing import Optional


class ManifestRepository:
    """Persists dev copy manifests as JSON files in {tempdir}/ms_access_dev/."""

    DEFAULT_BACKUP_BASE = os.path.join(tempfile.gettempdir(), "ms_access_dev")

    def __init__(self, backup_base: str | None = None) -> None:
        self._backup_base = backup_base or self.DEFAULT_BACKUP_BASE
        os.makedirs(self._backup_base, exist_ok=True)

    def _manifest_path(self, db_path: str) -> str:
        """Compute manifest file path for a given database path."""
        short_hash = hashlib.md5(db_path.encode()).hexdigest()[:8]
        return os.path.join(self._backup_base, "ms_access_dev", f"{short_hash}.json")

    def save_manifest(self, db_path: str, manifest: dict) -> bool:
        """Write manifest JSON."""
        try:
            manifest_dir = os.path.join(self._backup_base, "ms_access_dev")
            os.makedirs(manifest_dir, exist_ok=True)
            path = self._manifest_path(db_path)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
            return True
        except Exception:
            return False

    def load_manifest(self, db_path: str) -> Optional[dict]:
        """Load manifest JSON."""
        try:
            path = self._manifest_path(db_path)
            if not os.path.exists(path):
                return None
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def delete_manifest(self, db_path: str) -> bool:
        """Delete manifest file."""
        try:
            path = self._manifest_path(db_path)
            if os.path.exists(path):
                os.unlink(path)
                return True
            return False
        except Exception:
            return False