"""Tests for DevCopyService — dev copy lifecycle and manifest management."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ms_access_mcp.services.dev_copy_service import DevCopyService
from ms_access_mcp.services.connection import ConnectionService


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

class FakeAdapter:
    """Minimal adapter for DevCopyService tests."""
    def __init__(self, linked_tables=None):
        self._linked_tables = linked_tables or {"success": True, "linked_tables": []}
        self._connected = False

    def connect(self, path):
        self._connected = True
        return True

    def disconnect(self):
        self._connected = False

    def is_connected(self):
        return self._connected

    def copy_database(self, src, dst):
        # Copy the file so size check passes
        try:
            with open(src, "rb") as f:
                data = f.read()
            with open(dst, "wb") as f:
                f.write(data)
            return True
        except Exception:
            return False

    def get_linked_tables(self):
        return self._linked_tables


class FakeConnectionService:
    """Minimal connection service for DevCopyService tests."""
    def __init__(self, current_db=None):
        self.current_database = current_db

    def disconnect(self):
        self.current_database = None

    def connect(self, path, adapter=None):
        self.current_database = path

    def reconnect(self, path):
        self.current_database = path


# ═══════════════════════════════════════════════════════════════════════
# Manifest CRUD
# ═══════════════════════════════════════════════════════════════════════

class TestManifestCrud:
    """save_manifest, load_manifest, delete_manifest."""

    def test_save_and_load_manifest(self, tmp_path):
        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        manifest = {
            "production_path": "/path/to/prod.accdb",
            "dev_path": "/path/to/dev.accdb",
            "created_at": "2025-01-01T00:00:00Z",
            "db_size_bytes": 12345,
            "has_linked_tables": False,
            "linked_table_count": 0,
            "deployed_at": None,
        }
        assert svc.save_manifest("/path/to/prod.accdb", manifest) is True
        loaded = svc.load_manifest("/path/to/prod.accdb")
        assert loaded is not None
        assert loaded["production_path"] == "/path/to/prod.accdb"
        assert loaded["dev_path"] == "/path/to/dev.accdb"

    def test_load_manifest_not_found(self, tmp_path):
        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        assert svc.load_manifest("/nonexistent/prod.accdb") is None

    def test_delete_manifest(self, tmp_path):
        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        manifest = {"production_path": "/p", "dev_path": "/d",
                     "created_at": "2025", "db_size_bytes": 0,
                     "has_linked_tables": False, "linked_table_count": 0,
                     "deployed_at": None}
        svc.save_manifest("/p", manifest)
        assert svc.delete_manifest("/p") is True
        assert svc.load_manifest("/p") is None

    def test_delete_manifest_not_found(self, tmp_path):
        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        assert svc.delete_manifest("/nonexistent.accdb") is False

    def test_manifest_path_is_deterministic(self, tmp_path):
        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        p1 = svc._manifest_path("/path/to/db.accdb")
        p2 = svc._manifest_path("/path/to/db.accdb")
        assert p1 == p2
        # Hash should be 8 chars
        assert len(os.path.basename(p1)) == 8 + 5  # hash + .json


# ═══════════════════════════════════════════════════════════════════════
# create_dev_copy
# ═══════════════════════════════════════════════════════════════════════

class TestCreateDevCopy:
    """create_dev_copy — full pipeline."""

    def test_creates_dev_copy_file(self, tmp_path):
        prod = tmp_path / "prod.accdb"
        prod.write_bytes(b"PROD DATABASE CONTENT" * 100)

        svc = DevCopyService()
        conn = FakeConnectionService(str(prod))
        adapter = FakeAdapter()

        result = svc.create_dev_copy(conn, adapter)
        assert result["success"] is True
        assert os.path.exists(result["dev_path"])
        assert os.path.getsize(result["dev_path"]) > 0

    def test_dev_copy_switches_connection(self, tmp_path):
        prod = tmp_path / "prod.accdb"
        prod.write_bytes(b"PROD" * 10)

        svc = DevCopyService()
        conn = FakeConnectionService(str(prod))
        adapter = FakeAdapter()

        result = svc.create_dev_copy(conn, adapter)
        assert result["success"] is True
        assert conn.current_database == result["dev_path"]

    def test_saves_manifest(self, tmp_path):
        prod = tmp_path / "prod.accdb"
        prod.write_bytes(b"PROD" * 10)

        svc = DevCopyService()
        conn = FakeConnectionService(str(prod))
        adapter = FakeAdapter()

        result = svc.create_dev_copy(conn, adapter)
        assert result["success"] is True
        manifest = svc.load_manifest(str(prod))
        assert manifest is not None
        assert manifest["dev_path"] == result["dev_path"]

    def test_dev_copy_already_active_rejects_second_call(self, tmp_path):
        """A second create_dev_copy from the prod path fails when a dev copy exists."""
        prod = tmp_path / "prod.accdb"
        prod.write_bytes(b"PROD" * 10)

        svc = DevCopyService()
        real_conn = ConnectionService()
        real_adapter = MagicMock()
        real_adapter.copy_database.return_value = True
        real_adapter.get_linked_tables.return_value = {"success": True, "linked_tables": []}
        real_adapter.connect.return_value = True

        real_conn.connect(str(prod), real_adapter)
        svc.create_dev_copy(real_conn, real_adapter)

        # Simulate going back to prod (e.g., after reviewing dev changes)
        real_conn.disconnect()
        real_conn.connect(str(prod), real_adapter)

        # Try to create another dev copy from prod — should be rejected
        result2 = svc.create_dev_copy(real_conn, real_adapter)
        assert result2["success"] is False
        assert "already active" in result2["error"].lower()

    def test_not_connected_error(self, tmp_path):
        svc = DevCopyService()
        from ms_access_mcp.services.connection import ConnectionService
        conn = ConnectionService()  # not connected
        result = svc.create_dev_copy(conn, MagicMock())
        assert result["success"] is False
        assert "Not connected" in result["error"]

    def test_linked_table_warning(self, tmp_path):
        prod = tmp_path / "prod.accdb"
        prod.write_bytes(b"PROD" * 10)

        adapter = FakeAdapter({
            "success": True,
            "linked_tables": [
                {"name": "tblODBC", "source_table": "RemoteData", "connect_string": "ODBC;DRIVER=..."}
            ] * 3
        })
        svc = DevCopyService()
        conn = FakeConnectionService(str(prod))

        result = svc.create_dev_copy(conn, adapter)
        assert result["success"] is True
        assert "linked" in result["warnings"][0].lower()


# ═══════════════════════════════════════════════════════════════════════
# deploy_dev_copy
# ═══════════════════════════════════════════════════════════════════════

class TestDeployDevCopy:
    """deploy_dev_copy — deploy dev copy back to production."""

    def test_deploy_creates_backup_and_overwrites_production(self, tmp_path):
        """Full deploy pipeline: backup + overwrite + delete manifest."""
        prod = tmp_path / "prod.accdb"
        prod.write_bytes(b"OLD" * 10)
        dev = tmp_path / "prod_dev.accdb"
        dev.write_bytes(b"NEW" * 10)

        svc = DevCopyService()
        svc._backup_base = str(tmp_path)

        # Set up manifest so deploy finds it via prod path
        svc.save_manifest(str(prod), {
            "production_path": str(prod),
            "dev_path": str(dev),
            "created_at": "2025",
            "db_size_bytes": 80,
            "has_linked_tables": False,
            "linked_table_count": 0,
            "deployed_at": None,
        })

        # Real adapter uses copy_database to copy files
        real_adapter = FakeAdapter()

        # Use ConnectionService to set up the production path as current_database
        from ms_access_mcp.services.connection import ConnectionService
        real_conn = ConnectionService()
        real_conn.connect(str(prod), real_adapter)

        result = svc.deploy_dev_copy(real_conn, real_adapter)
        assert result["success"] is True
        assert os.path.exists(result["bak_path"])  # .bak created
        assert prod.read_bytes() == b"NEW" * 10  # prod overwritten
        assert svc.load_manifest(str(prod)) is None  # manifest deleted

    def test_deploy_no_manifest_returns_error(self, tmp_path):
        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        from ms_access_mcp.services.connection import ConnectionService
        real_conn = ConnectionService()
        real_adapter = FakeAdapter()
        real_conn.connect(str(tmp_path / "p.accdb"), real_adapter)
        result = svc.deploy_dev_copy(real_conn, real_adapter)
        assert result["success"] is False
        assert "No active dev copy" in result["error"]


class TestDiscardDevCopy:
    """discard_dev_copy — discard dev copy and reconnect to production."""

    def test_discard_removes_dev_file_and_restores_production(self, tmp_path):
        """Full discard pipeline: delete dev + reconnect to prod."""
        prod = tmp_path / "prod.accdb"
        prod.write_bytes(b"PROD" * 10)
        dev = tmp_path / "prod_dev.accdb"
        dev.write_bytes(b"DEV" * 10)

        svc = DevCopyService()
        svc._backup_base = str(tmp_path)

        svc.save_manifest(str(prod), {
            "production_path": str(prod), "dev_path": str(dev),
            "created_at": "2025", "db_size_bytes": 80,
            "has_linked_tables": False, "linked_table_count": 0,
            "deployed_at": None,
        })

        real_adapter = FakeAdapter()
        from ms_access_mcp.services.connection import ConnectionService
        real_conn = ConnectionService()
        real_conn.connect(str(dev), real_adapter)

        result = svc.discard_dev_copy(real_conn, real_adapter)
        assert result["success"] is True
        assert not os.path.exists(dev)  # dev file deleted
        assert real_conn.current_database == str(prod)  # reconnects to prod
        assert svc.load_manifest(str(prod)) is None  # manifest deleted

    def test_discard_no_manifest_returns_error(self, tmp_path):
        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        from ms_access_mcp.services.connection import ConnectionService
        real_conn = ConnectionService()
        real_adapter = FakeAdapter()
        real_conn.connect(str(tmp_path / "p.accdb"), real_adapter)
        result = svc.discard_dev_copy(real_conn, real_adapter)
        assert result["success"] is False
        assert "No active dev copy" in result["error"]


# ═══════════════════════════════════════════════════════════════════════
# discard_dev_copy
# ═══════════════════════════════════════════════════════════════════════

class TestDiscardDevCopy:
    """discard_dev_copy — discard dev copy and reconnect to production."""

    def test_discard_removes_dev_file_restores_connection(self, tmp_path):
        """Full discard: delete dev copy file + reconnect to production.

        discard_dev_copy with production_path=None uses conn.current_database.
        When conn is connected to the dev copy, current_database=dev_path.
        Since the manifest is keyed by production_path, we pass production_path
        explicitly so the manifest lookup finds it.
        """
        prod = tmp_path / "prod.accdb"
        prod.write_bytes(b"PROD" * 10)
        dev = tmp_path / "prod_dev.accdb"
        dev.write_bytes(b"DEV" * 10)

        svc = DevCopyService()
        svc._backup_base = str(tmp_path)

        svc.save_manifest(str(prod), {
            "production_path": str(prod), "dev_path": str(dev),
            "created_at": "2025", "db_size_bytes": 80,
            "has_linked_tables": False, "linked_table_count": 0,
            "deployed_at": None,
        })

        real_adapter = FakeAdapter()
        from ms_access_mcp.services.connection import ConnectionService
        real_conn = ConnectionService()
        real_conn.connect(str(dev), real_adapter)

        # Pass production_path explicitly so the manifest lookup works
        result = svc.discard_dev_copy(real_conn, real_adapter, production_path=str(prod))
        assert result["success"] is True
        assert not os.path.exists(dev)
        assert real_conn.current_database == str(prod)
        assert svc.load_manifest(str(prod)) is None

    def test_discard_no_manifest(self, tmp_path):
        svc = DevCopyService()
        real_conn = ConnectionService()
        real_adapter = MagicMock()
        real_adapter.connect.return_value = True
        real_conn.connect(str(tmp_path / "p.accdb"), real_adapter)
        result = svc.discard_dev_copy(real_conn, real_adapter)
        assert result["success"] is False
        assert "No active dev copy" in result["error"]


# ═══════════════════════════════════════════════════════════════════════
# get_dev_copy_status
# ═══════════════════════════════════════════════════════════════════════

class TestGetDevCopyStatus:
    def test_no_manifest(self, tmp_path):
        svc = DevCopyService()
        result = svc.get_dev_copy_status(str(tmp_path / "p.accdb"))
        assert result["active"] is False

    def test_active_dev_copy(self, tmp_path):
        prod = tmp_path / "prod.accdb"
        prod.write_bytes(b"PROD" * 10)
        dev = tmp_path / "prod_dev.accdb"
        dev.write_bytes(b"DEV" * 10)

        svc = DevCopyService()
        svc.save_manifest(str(prod), {
            "production_path": str(prod), "dev_path": str(dev),
            "created_at": "2025-01-01T00:00:00Z",
            "db_size_bytes": 80,
            "has_linked_tables": True,
            "linked_table_count": 2,
            "deployed_at": None,
        })

        result = svc.get_dev_copy_status(str(prod))
        assert result["active"] is True
        assert result["production_path"] == str(prod)
        assert result["dev_path"] == str(dev)
        assert result["has_linked_tables"] is True
        assert result["linked_table_count"] == 2


# ═══════════════════════════════════════════════════════════════════════
# VBA Backup / Restore
# ═══════════════════════════════════════════════════════════════════════

class TestModuleBackup:
    def test_export_module_backup_not_found(self, tmp_path):
        adapter = MagicMock()
        adapter.export_module_to_text.return_value = ""
        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        result = svc.export_module_backup(adapter, "NonExistentModule")
        assert result["success"] is False

    def test_export_module_backup_success(self, tmp_path):
        adapter = MagicMock()
        adapter.export_module_to_text.return_value = "Public Sub Test()\nEnd Sub"
        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        result = svc.export_module_backup(adapter, "modTest", str(tmp_path))
        assert result["success"] is True
        assert os.path.exists(result["backup_path"])
        assert result["file_size_bytes"] > 0

    def test_import_module_file_not_found(self, tmp_path):
        adapter = MagicMock()
        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        result = svc.import_module_from_text(adapter, "modTest", "/nonexistent/modTest.bas")
        assert result["success"] is False
        assert "not found" in result["error"].lower()


# ═══════════════════════════════════════════════════════════════════════
# Form Backup / Restore
# ═══════════════════════════════════════════════════════════════════════

class TestFormBackup:
    def test_export_form_backup_not_found(self, tmp_path):
        adapter = MagicMock()
        adapter.export_form_to_text.return_value = ""
        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        result = svc.export_form_backup(adapter, "NonExistentForm")
        assert result["success"] is False

    def test_export_form_backup_success(self, tmp_path):
        adapter = MagicMock()
        adapter.export_form_to_text.return_value = "FORM DESIGN TEXT"
        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        result = svc.export_form_backup(adapter, "TestForm", str(tmp_path))
        assert result["success"] is True
        assert os.path.exists(result["backup_path"])

    def test_import_form_file_not_found(self, tmp_path):
        adapter = MagicMock()
        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        result = svc.import_form_from_text(adapter, "TestForm", "/nonexistent/form.txt")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_import_form_success(self, tmp_path):
        form_file = tmp_path / "TestForm.txt"
        form_file.write_text("FORM DESIGN CONTENT")

        adapter = MagicMock()
        adapter.form_exists.return_value = False
        adapter.import_form_from_text.return_value = True

        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        result = svc.import_form_from_text(adapter, "TestForm", str(form_file))
        assert result["success"] is True


# ═══════════════════════════════════════════════════════════════════════
# Report Backup / Restore
# ═══════════════════════════════════════════════════════════════════════

class TestReportBackup:
    def test_export_report_backup_not_found(self, tmp_path):
        adapter = MagicMock()
        adapter.export_report_to_text.return_value = ""
        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        result = svc.export_report_backup(adapter, "NonExistentReport")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_export_report_backup_success(self, tmp_path):
        adapter = MagicMock()
        adapter.export_report_to_text.return_value = "REPORT DESIGN TEXT"
        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        result = svc.export_report_backup(adapter, "TestReport", str(tmp_path))
        assert result["success"] is True
        assert os.path.exists(result["backup_path"])
        assert result["file_size_bytes"] > 0

    def test_import_report_file_not_found(self, tmp_path):
        adapter = MagicMock()
        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        result = svc.import_report_from_file(adapter, "TestReport", "/nonexistent/report.txt")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_import_report_deletes_existing_and_imports(self, tmp_path):
        report_file = tmp_path / "TestReport.txt"
        report_file.write_text("REPORT DESIGN CONTENT")

        adapter = MagicMock()
        adapter.report_exists.return_value = True
        adapter.delete_report.return_value = True
        adapter.import_report_from_text.return_value = True

        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        result = svc.import_report_from_file(adapter, "TestReport", str(report_file))
        assert result["success"] is True
        adapter.delete_report.assert_called_once_with("TestReport")
        adapter.import_report_from_text.assert_called_once()

    def test_import_report_creates_new_if_not_exists(self, tmp_path):
        report_file = tmp_path / "NewReport.txt"
        report_file.write_text("NEW REPORT DESIGN")

        adapter = MagicMock()
        adapter.report_exists.return_value = False
        adapter.import_report_from_text.return_value = True

        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        result = svc.import_report_from_file(adapter, "NewReport", str(report_file))
        assert result["success"] is True
        adapter.delete_report.assert_not_called()

    def test_restore_report_backup_delegates_to_import(self, tmp_path):
        report_file = tmp_path / "ReportBackup.txt"
        report_file.write_text("REPORT BACKUP CONTENT")

        adapter = MagicMock()
        adapter.report_exists.return_value = False
        adapter.import_report_from_text.return_value = True

        svc = DevCopyService()
        svc._backup_base = str(tmp_path)

        with patch.object(svc, "import_report_from_file", return_value={"success": True, "report_name": "TestReport"}) as mock_restore:
            result = svc.restore_report_backup(adapter, "TestReport", str(report_file))
            mock_restore.assert_called_once_with(adapter, "TestReport", str(report_file))
            assert result["success"] is True


# ═══════════════════════════════════════════════════════════════════════
# Backup Directory
# ═══════════════════════════════════════════════════════════════════════

class TestBackupDirectory:
    def test_get_backup_dir_creates_if_missing(self, tmp_path):
        svc = DevCopyService()
        svc._backup_base = str(tmp_path)
        backup_dir = svc.get_backup_dir()
        assert os.path.isdir(backup_dir)
        assert backup_dir.endswith("backups")

    def test_backup_dir_uses_tempdir_default(self):
        svc = DevCopyService()
        backup_dir = svc.get_backup_dir()
        assert tempfile.gettempdir() in backup_dir
        assert backup_dir.endswith("backups")