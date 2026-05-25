"""Tests for DevCopyService manifest CRUD operations."""
import pytest
import json
import shutil
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from ms_access_mcp.services.dev_copy_service import DevCopyService


class TestDevCopyServiceManifestCRUD:
    """Tests for DevCopyService manifest JSON file operations."""

    def test_save_manifest_creates_json_file(self, tmp_path):
        """save_manifest() writes correct JSON to {tempdir}/ms_access_dev/{hash}.json."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        manifest = {
            "production_path": "C:\\databases\\MyApp.accdb",
            "dev_path": str(tmp_path / "myapp_dev.accdb"),
            "created_at": "2026-05-24T13:00:00Z",
            "db_size_bytes": 52428800,
            "has_linked_tables": False,
            "linked_table_count": 0,
            "deployed_at": None,
        }

        result = service.save_manifest("C:\\databases\\MyApp.accdb", manifest)

        assert result is True
        # Hash of path: md5("C:\\databases\\MyApp.accdb")[:8]
        manifest_path = service._manifest_path("C:\\databases\\MyApp.accdb")
        assert os.path.exists(manifest_path)
        with open(manifest_path) as f:
            saved = json.load(f)
        assert saved["production_path"] == "C:\\databases\\MyApp.accdb"
        assert saved["dev_path"] == str(tmp_path / "myapp_dev.accdb")

    def test_save_manifest_creates_directory(self, tmp_path):
        """save_manifest() creates the ms_access_dev directory if missing."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        manifest = {
            "production_path": "C:\\test\\app.accdb",
            "dev_path": str(tmp_path / "dev.accdb"),
            "created_at": "2026-05-24T13:00:00Z",
            "db_size_bytes": 1024,
            "has_linked_tables": False,
            "linked_table_count": 0,
            "deployed_at": None,
        }

        service.save_manifest("C:\\test\\app.accdb", manifest)

        manifest_path = service._manifest_path("C:\\test\\app.accdb")
        assert os.path.exists(manifest_path)

    def test_load_manifest_returns_correct_data(self, tmp_path):
        """load_manifest() reads and parses the JSON manifest file."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        manifest = {
            "production_path": "C:\\databases\\MyApp.accdb",
            "dev_path": str(tmp_path / "myapp_dev.accdb"),
            "created_at": "2026-05-24T13:00:00Z",
            "db_size_bytes": 52428800,
            "has_linked_tables": True,
            "linked_table_count": 3,
            "deployed_at": None,
        }
        service.save_manifest("C:\\databases\\MyApp.accdb", manifest)

        loaded = service.load_manifest("C:\\databases\\MyApp.accdb")

        assert loaded is not None
        assert loaded["production_path"] == "C:\\databases\\MyApp.accdb"
        assert loaded["dev_path"] == str(tmp_path / "myapp_dev.accdb")
        assert loaded["has_linked_tables"] is True
        assert loaded["linked_table_count"] == 3

    def test_load_manifest_returns_none_when_not_found(self, tmp_path):
        """load_manifest() returns None if manifest file does not exist."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        result = service.load_manifest("C:\\nonexistent\\app.accdb")

        assert result is None

    def test_delete_manifest_removes_file(self, tmp_path):
        """delete_manifest() removes the manifest JSON file."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        manifest = {
            "production_path": "C:\\databases\\MyApp.accdb",
            "dev_path": str(tmp_path / "myapp_dev.accdb"),
            "created_at": "2026-05-24T13:00:00Z",
            "db_size_bytes": 52428800,
            "has_linked_tables": False,
            "linked_table_count": 0,
            "deployed_at": None,
        }
        service.save_manifest("C:\\databases\\MyApp.accdb", manifest)
        manifest_path = service._manifest_path("C:\\databases\\MyApp.accdb")
        assert os.path.exists(manifest_path)

        result = service.delete_manifest("C:\\databases\\MyApp.accdb")

        assert result is True
        assert not os.path.exists(manifest_path)

    def test_delete_manifest_returns_false_when_not_found(self, tmp_path):
        """delete_manifest() returns False if manifest file does not exist."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        result = service.delete_manifest("C:\\nonexistent\\app.accdb")

        assert result is False

    def test_manifest_path_uses_md5_hash(self, tmp_path):
        """_manifest_path() generates correct path with md5 hash."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        path = service._manifest_path("C:\\databases\\MyApp.accdb")

        import hashlib
        expected_hash = hashlib.md5("C:\\databases\\MyApp.accdb".encode()).hexdigest()[:8]
        expected = tmp_path / "ms_access_dev" / f"{expected_hash}.json"
        assert path == str(expected)

    def test_manifest_path_different_for_different_paths(self, tmp_path):
        """Two different db paths produce different manifest paths."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        path1 = service._manifest_path("C:\\databases\\app1.accdb")
        path2 = service._manifest_path("C:\\databases\\app2.accdb")

        assert path1 != path2


class TestDevCopyServiceBackupDir:
    """Tests for get_backup_dir()."""

    def test_get_backup_dir_returns_correct_path(self, tmp_path):
        """get_backup_dir() returns {backup_base}/backups/ path."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        result = service.get_backup_dir()

        expected = os.path.join(str(tmp_path), "backups")
        assert result == expected

    def test_get_backup_dir_creates_directory_if_missing(self, tmp_path):
        """get_backup_dir() creates the backups directory if it does not exist."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        backups_path = os.path.join(str(tmp_path), "backups")
        assert not os.path.exists(backups_path)

        service.get_backup_dir()

        assert os.path.isdir(backups_path)

    def test_get_backup_dir_idempotent(self, tmp_path):
        """get_backup_dir() is safe to call multiple times."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        result1 = service.get_backup_dir()
        result2 = service.get_backup_dir()

        assert result1 == result2
        assert os.path.isdir(result1)


# ========================================================================
# Full DB Copy Pipeline Tests — create_dev_copy()
# ========================================================================


class TestCreateDevCopy:
    """Tests for DevCopyService.create_dev_copy()."""

    def test_create_dev_copy_happy_path(self, tmp_path):
        """create_dev_copy() copies DB, writes manifest, switches connection."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        # Create a fake prod DB
        prod_db = tmp_path / "MyApp.accdb"
        prod_db.write_bytes(b"FAKE ACCESS DB CONTENT" * 100)

        mock_conn = MagicMock()
        mock_conn.current_database = str(prod_db)
        mock_conn.adapter = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.copy_database.return_value = True
        mock_adapter.get_linked_tables.return_value = {"success": True, "linked_tables": []}

        result = service.create_dev_copy(mock_conn, mock_adapter)

        assert result["success"] is True
        assert "dev_path" in result
        assert "manifest_path" in result
        # Should have copied the file
        mock_adapter.copy_database.assert_called_once()
        # Should have disconnected and reconnected
        mock_conn.disconnect.assert_called_once()
        mock_conn.connect.assert_called_once()
        # Manifest should be saved
        manifest_path = service._manifest_path(str(prod_db))
        assert os.path.exists(manifest_path)

    def test_create_dev_copy_already_active_error(self, tmp_path):
        """create_dev_copy() returns error if dev copy already active."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        prod_db = tmp_path / "MyApp.accdb"
        prod_db.write_bytes(b"FAKE DB")

        # Simulate existing manifest (dev copy already active)
        manifest = {
            "production_path": str(prod_db),
            "dev_path": str(tmp_path / "dev.accdb"),
            "created_at": "2026-05-24T10:00:00Z",
            "db_size_bytes": 100,
            "has_linked_tables": False,
            "linked_table_count": 0,
            "deployed_at": None,
        }
        service.save_manifest(str(prod_db), manifest)

        mock_conn = MagicMock()
        mock_conn.current_database = str(prod_db)
        mock_conn.adapter = MagicMock()
        mock_adapter = MagicMock()

        result = service.create_dev_copy(mock_conn, mock_adapter)

        assert result["success"] is False
        assert "already active" in result["error"].lower()

    def test_create_dev_copy_large_db_warning(self, tmp_path):
        """create_dev_copy() includes warning for DB > 500MB."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        # Create a large fake DB (> 500 MB)
        prod_db = tmp_path / "LargeApp.accdb"
        # 600 MB worth of data
        prod_db.write_bytes(b"X" * (600 * 1024 * 1024))

        mock_conn = MagicMock()
        mock_conn.current_database = str(prod_db)
        mock_conn.adapter = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.copy_database.side_effect = lambda src, dst: shutil.copy2(src, dst)
        mock_adapter.get_linked_tables.return_value = {"success": True, "linked_tables": []}

        # Patch _db_size_mb to return > 500 MB and os.path.exists for manifest save
        with patch.object(service, "_db_size_mb", return_value=600.0), \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=600 * 1024 * 1024):
            result = service.create_dev_copy(mock_conn, mock_adapter)

        assert result["success"] is True
        assert "warnings" in result
        assert "large" in result["warnings"][0].lower() or "500" in result["warnings"][0]




# ========================================================================
# Full DB Copy Pipeline Tests — deploy_dev_copy()
# ========================================================================


class TestDeployDevCopy:
    """Tests for DevCopyService.deploy_dev_copy()."""

    def test_deploy_dev_copy_happy_path(self, tmp_path):
        """deploy_dev_copy() backs up prod, copies dev over, reconnects, removes manifest."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        # Set up prod and dev DBs using the EXACT dev_path that create_dev_copy would compute
        prod_db = tmp_path / "MyApp.accdb"
        prod_db.write_bytes(b"ORIGINAL PROD CONTENT")

        # Compute the dev path exactly as _dev_copy_path() does
        import hashlib
        short_hash = hashlib.md5(str(prod_db).encode()).hexdigest()[:8]
        dev_dir = tmp_path / "ms_access_dev" / short_hash
        dev_dir.mkdir(parents=True, exist_ok=True)
        dev_db = dev_dir / "MyApp_dev.accdb"
        dev_db.write_bytes(b"MODIFIED DEV CONTENT")

        # Create manifest using the SAME path that create_dev_copy would use
        manifest = {
            "production_path": str(prod_db),
            "dev_path": str(dev_db),
            "created_at": "2026-05-24T10:00:00Z",
            "db_size_bytes": 100,
            "has_linked_tables": False,
            "linked_table_count": 0,
            "deployed_at": None,
        }
        service.save_manifest(str(prod_db), manifest)

        mock_conn = MagicMock()
        mock_conn.current_database = str(dev_db)
        mock_conn.adapter = MagicMock()
        mock_adapter = MagicMock()
        # Make copy_database actually copy files
        mock_adapter.copy_database.side_effect = lambda src, dst: shutil.copy2(src, dst)

        result = service.deploy_dev_copy(mock_conn, mock_adapter, production_path=str(prod_db))

        assert result["success"] is True
        # .bak should exist
        bak_file = str(prod_db) + ".bak"
        assert os.path.exists(bak_file)
        # Prod should have dev content
        assert prod_db.read_bytes() == b"MODIFIED DEV CONTENT"
        # Reconnect called with prod path
        mock_conn.reconnect.assert_called_once_with(str(prod_db))
        # Manifest deleted
        manifest_path = service._manifest_path(str(prod_db))
        assert not os.path.exists(manifest_path)

    def test_deploy_dev_copy_no_dev_copy_error(self, tmp_path):
        """deploy_dev_copy() returns error when no active dev copy."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        mock_conn = MagicMock()
        mock_conn.current_database = "C:\\nonexistent\\app.accdb"
        mock_conn.adapter = MagicMock()
        mock_adapter = MagicMock()

        result = service.deploy_dev_copy(mock_conn, mock_adapter)

        assert result["success"] is False
        assert "no active dev copy" in result["error"].lower()

    def test_deploy_dev_copy_integrity_validation(self, tmp_path):
        """deploy_dev_copy() validates dev DB exists and is non-empty before deploying."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        prod_db = tmp_path / "MyApp.accdb"
        prod_db.write_bytes(b"ORIGINAL")

        # Dev copy is missing/empty
        dev_db = tmp_path / "ms_access_dev" / "dev_copy" / "MyApp_dev.accdb"
        dev_db.parent.mkdir(parents=True, exist_ok=True)
        # Don't write anything — empty file

        manifest = {
            "production_path": str(prod_db),
            "dev_path": str(dev_db),
            "created_at": "2026-05-24T10:00:00Z",
            "db_size_bytes": 0,
            "has_linked_tables": False,
            "linked_table_count": 0,
            "deployed_at": None,
        }
        service.save_manifest(str(prod_db), manifest)

        mock_conn = MagicMock()
        mock_conn.current_database = str(dev_db)
        mock_conn.adapter = MagicMock()
        mock_adapter = MagicMock()

        result = service.deploy_dev_copy(mock_conn, mock_adapter, production_path=str(prod_db))

        assert result["success"] is False
        assert "empty" in result["error"].lower() or "not found" in result["error"].lower()


# ========================================================================
# Full DB Copy Pipeline Tests — discard_dev_copy()
# ========================================================================


class TestDiscardDevCopy:
    """Tests for DevCopyService.discard_dev_copy()."""

    def test_discard_dev_copy_happy_path(self, tmp_path):
        """discard_dev_copy() deletes dev copy, removes manifest, reconnects to prod."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        prod_db = tmp_path / "MyApp.accdb"
        prod_db.write_bytes(b"ORIGINAL PROD")
        dev_db = tmp_path / "ms_access_dev" / "dev" / "MyApp_dev.accdb"
        dev_db.parent.mkdir(parents=True, exist_ok=True)
        dev_db.write_bytes(b"DEV COPY TO DISCARD")

        manifest = {
            "production_path": str(prod_db),
            "dev_path": str(dev_db),
            "created_at": "2026-05-24T10:00:00Z",
            "db_size_bytes": 100,
            "has_linked_tables": False,
            "linked_table_count": 0,
            "deployed_at": None,
        }
        service.save_manifest(str(prod_db), manifest)

        mock_conn = MagicMock()
        mock_conn.current_database = str(dev_db)
        mock_conn.adapter = MagicMock()
        mock_adapter = MagicMock()

        result = service.discard_dev_copy(mock_conn, mock_adapter, production_path=str(prod_db))

        assert result["success"] is True
        # Dev copy deleted
        assert not dev_db.exists()
        # Manifest deleted
        manifest_path = service._manifest_path(str(prod_db))
        assert not os.path.exists(manifest_path)
        # Reconnected to prod
        mock_conn.reconnect.assert_called_once_with(str(prod_db))

    def test_discard_dev_copy_no_dev_copy_error(self, tmp_path):
        """discard_dev_copy() returns error when no active dev copy."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        mock_conn = MagicMock()
        mock_conn.current_database = "C:\\nonexistent\\app.accdb"
        mock_conn.adapter = MagicMock()
        mock_adapter = MagicMock()

        result = service.discard_dev_copy(mock_conn, mock_adapter)

        assert result["success"] is False
        assert "no active dev copy" in result["error"].lower()


# ========================================================================
# Full DB Copy Pipeline Tests — get_dev_copy_status()
# ========================================================================


class TestGetDevCopyStatus:
    """Tests for DevCopyService.get_dev_copy_status()."""

    def test_get_dev_copy_status_active(self, tmp_path):
        """get_dev_copy_status() returns active state with paths and timestamps."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        prod_db = tmp_path / "MyApp.accdb"
        prod_db.write_bytes(b"FAKE DB" * 10)
        dev_db = tmp_path / "ms_access_dev" / "hash123" / "MyApp_dev.accdb"
        dev_db.parent.mkdir(parents=True, exist_ok=True)
        dev_db.write_bytes(b"DEV")

        manifest = {
            "production_path": str(prod_db),
            "dev_path": str(dev_db),
            "created_at": "2026-05-24T10:00:00Z",
            "db_size_bytes": 500,
            "has_linked_tables": True,
            "linked_table_count": 2,
            "deployed_at": None,
        }
        service.save_manifest(str(prod_db), manifest)

        result = service.get_dev_copy_status(str(prod_db))

        assert result["active"] is True
        assert result["production_path"] == str(prod_db)
        assert result["dev_path"] == str(dev_db)
        assert result["created_at"] == "2026-05-24T10:00:00Z"
        assert result["db_size_bytes"] == 500
        assert result["has_linked_tables"] is True
        assert result["linked_table_count"] == 2

    def test_get_dev_copy_status_inactive(self, tmp_path):
        """get_dev_copy_status() returns inactive when no manifest exists."""
        service = DevCopyService()
        service._backup_base = str(tmp_path)

        result = service.get_dev_copy_status("C:\\databases\\NoManifest.accdb")

        assert result["active"] is False
        assert "dev_path" not in result or result.get("dev_path") is None