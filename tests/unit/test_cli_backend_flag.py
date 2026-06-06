"""Verify CLI commands accept --backend and route through BackendSelector.

Tests ensure _get_adapter delegates to BackendSelector.get_adapter with the
right backend and capabilities. No actual DB connections are made — we patch
BackendSelector.get_adapter at its source module.
"""
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from ms_access_mcp.cli.main import app, _get_adapter


runner = CliRunner()


class TestGetAdapterFunction:
    """Unit tests for the _get_adapter helper — routes through BackendSelector."""

    def test_default_backend_routes_to_odbc(self, monkeypatch):
        """_get_adapter() with no backend arg calls BackendSelector with backend='odbc'."""
        captured = {}

        def _spy(db_path, backend=None, capabilities=None):
            captured["db_path"] = db_path
            captured["backend"] = backend
            captured["capabilities"] = capabilities
            mock = MagicMock()
            mock.connect.return_value = True
            return mock

        monkeypatch.setattr(
            "ms_access_mcp.services.backend_selector.BackendSelector.get_adapter",
            _spy
        )
        adapter = _get_adapter("/tmp/test.accdb")
        assert captured["backend"] == "odbc"
        assert captured["db_path"] == "/tmp/test.accdb"
        assert adapter is not None

    def test_backend_odbc_explicit(self, monkeypatch):
        """_get_adapter(..., backend='odbc') calls BackendSelector.get_adapter(backend='odbc')."""
        captured = {}

        def _spy(db_path, backend=None, capabilities=None):
            captured["db_path"] = db_path
            captured["backend"] = backend
            captured["capabilities"] = capabilities
            mock = MagicMock()
            mock.connect.return_value = True
            return mock

        monkeypatch.setattr(
            "ms_access_mcp.services.backend_selector.BackendSelector.get_adapter",
            _spy
        )
        adapter = _get_adapter("/tmp/test.accdb", backend="odbc")
        assert captured["backend"] == "odbc"
        assert captured["db_path"] == "/tmp/test.accdb"

    def test_backend_com_routes_to_selector(self, monkeypatch):
        """_get_adapter(..., backend='com') calls BackendSelector.get_adapter(backend='com')."""
        captured = {}

        def _spy(db_path, backend=None, capabilities=None):
            captured["db_path"] = db_path
            captured["backend"] = backend
            mock = MagicMock()
            mock.connect.return_value = True
            return mock

        monkeypatch.setattr(
            "ms_access_mcp.services.backend_selector.BackendSelector.get_adapter",
            _spy
        )
        adapter = _get_adapter("/tmp/test.accdb", backend="com")
        assert captured["backend"] == "com"


class TestCliExportAllBackend:
    """Verify export-all routes through BackendSelector."""

    def test_export_all_default_uses_odbc(self, tmp_path, monkeypatch):
        """export-all without --backend calls selector with backend='odbc'."""
        captured = {}

        def _spy(db_path, backend=None, capabilities=None):
            captured["db_path"] = db_path
            captured["backend"] = backend
            captured["capabilities"] = capabilities
            mock = MagicMock()
            mock.connect.return_value = True
            mock.is_connected.return_value = True
            return mock

        monkeypatch.setattr(
            "ms_access_mcp.services.backend_selector.BackendSelector.get_adapter",
            _spy
        )
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator") as MockOrch:
            MockOrch.return_value.export_all.return_value = {"success": True, "exported": 0}
            result = runner.invoke(app, [
                "export-all",
                "--dir", str(tmp_path),
                "--db", "/tmp/test.accdb",
            ])

        assert result.exit_code == 0, result.stdout
        assert captured["backend"] == "odbc"

    def test_export_all_com_flag_uses_com(self, tmp_path, monkeypatch):
        """export-all --backend com calls selector with backend='com'."""
        captured = {}

        def _spy(db_path, backend=None, capabilities=None):
            captured["db_path"] = db_path
            captured["backend"] = backend
            mock = MagicMock()
            mock.connect.return_value = True
            mock.is_connected.return_value = True
            return mock

        monkeypatch.setattr(
            "ms_access_mcp.services.backend_selector.BackendSelector.get_adapter",
            _spy
        )
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator") as MockOrch:
            MockOrch.return_value.export_all.return_value = {"success": True, "exported": 0}
            result = runner.invoke(app, [
                "export-all",
                "--dir", str(tmp_path),
                "--db", "/tmp/test.accdb",
                "--backend", "com",
            ])

        assert result.exit_code == 0, result.stdout
        assert captured["backend"] == "com"

    def test_export_all_without_vba_passes_no_vba_capability(self, tmp_path, monkeypatch):
        """export-all (no --include-vba) calls selector with no VBA capability."""
        captured = {}

        def _spy(db_path, backend=None, capabilities=None):
            captured["db_path"] = db_path
            captured["backend"] = backend
            captured["capabilities"] = capabilities
            mock = MagicMock()
            mock.connect.return_value = True
            mock.is_connected.return_value = True
            return mock

        monkeypatch.setattr(
            "ms_access_mcp.services.backend_selector.BackendSelector.get_adapter",
            _spy
        )
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator") as MockOrch:
            MockOrch.return_value.export_all.return_value = {"success": True, "exported": 0}
            result = runner.invoke(app, [
                "export-all",
                "--dir", str(tmp_path),
                "--db", "/tmp/test.accdb",
            ])

        assert result.exit_code == 0, result.stdout
        # export_all without --include-vba should not pass VBA caps
        assert captured["capabilities"] is None


class TestCliCompareVersioningBackend:
    """Verify compare-versioning routes through BackendSelector."""

    def test_compare_default_uses_odbc(self, tmp_path, monkeypatch):
        """compare-versioning without --backend calls selector with backend='odbc'."""
        captured = {}

        def _spy(db_path, backend=None, capabilities=None):
            captured["backend"] = backend
            mock = MagicMock()
            mock.connect.return_value = True
            mock.is_connected.return_value = True
            return mock

        monkeypatch.setattr(
            "ms_access_mcp.services.backend_selector.BackendSelector.get_adapter",
            _spy
        )
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator") as MockOrch:
            MockOrch.return_value.compare.return_value = {
                "success": True, "new": [], "missing": [], "changed": [], "unchanged": []
            }
            result = runner.invoke(app, [
                "compare-versioning",
                "--dir", str(tmp_path),
                "--db", "/tmp/test.accdb",
            ])

        assert result.exit_code == 0, result.stdout
        assert captured["backend"] == "odbc"

    def test_compare_com_flag_uses_com(self, tmp_path, monkeypatch):
        """compare-versioning --backend com calls selector with backend='com'."""
        captured = {}

        def _spy(db_path, backend=None, capabilities=None):
            captured["backend"] = backend
            mock = MagicMock()
            mock.connect.return_value = True
            mock.is_connected.return_value = True
            return mock

        monkeypatch.setattr(
            "ms_access_mcp.services.backend_selector.BackendSelector.get_adapter",
            _spy
        )
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator") as MockOrch:
            MockOrch.return_value.compare.return_value = {
                "success": True, "new": [], "missing": [], "changed": [], "unchanged": []
            }
            result = runner.invoke(app, [
                "compare-versioning",
                "--dir", str(tmp_path),
                "--db", "/tmp/test.accdb",
                "--backend", "com",
            ])

        assert result.exit_code == 0, result.stdout
        assert captured["backend"] == "com"


class TestCliExportVbaBackend:
    """Verify export-vba routes through BackendSelector."""

    def test_export_vba_com_flag(self, tmp_path, monkeypatch):
        """export-vba --backend com calls selector with VBA_CAPS."""
        captured = {}

        def _spy(db_path, backend=None, capabilities=None):
            captured["db_path"] = db_path
            captured["backend"] = backend
            captured["capabilities"] = capabilities
            mock = MagicMock()
            mock.connect.return_value = True
            mock.export_module_to_text.return_value = "Sub Test()\nEnd Sub"
            return mock

        monkeypatch.setattr(
            "ms_access_mcp.services.backend_selector.BackendSelector.get_adapter",
            _spy
        )
        result = runner.invoke(app, [
            "export-vba", "Module1",
            "--db", "/tmp/test.accdb",
            "--backend", "com",
        ])

        assert result.exit_code == 0, result.stdout
        assert captured["backend"] == "com"
        # export_vba should pass VBA_CAPS
        from ms_access_mcp.services.backend_selector import VBA_CAPS
        assert captured["capabilities"] == VBA_CAPS

    def test_export_vba_odbc_raises_mismatch(self, tmp_path, monkeypatch):
        """export-vba --backend odbc raises BackendCapabilityMismatchError."""
        monkeypatch.setattr(
            "ms_access_mcp.services.backend_selector.BackendSelector.get_adapter",
            lambda db_path, backend=None, capabilities=None: (
                __import__("ms_access_mcp.services.backend_selector",
                            fromlist=["BackendCapabilityMismatchError"]
                ).BackendCapabilityMismatchError("VBA requires COM")
            )
        )
        result = runner.invoke(app, [
            "export-vba", "Module1",
            "--db", "/tmp/test.accdb",
            "--backend", "odbc",
        ])

        assert result.exit_code != 0


class TestCliExportAllVbaMismatch:
    """REQ-13 / T2.2: export-all --backend odbc with VBA capability mismatch."""

    def test_export_all_odbc_succeeds_without_vba_modules(self, tmp_path, monkeypatch):
        """export-all --backend odbc succeeds when no VBA modules are exported."""
        # When ODBC is explicitly requested, selector returns OdbcAdapter
        # (VBA export is separate command, so export-all with ODBC should not fail)
        mock_adapter = MagicMock()
        mock_adapter.connect.return_value = True
        mock_adapter.is_connected.return_value = True

        def _select(db_path, backend=None, capabilities=None):
            from ms_access_mcp.adapters.odbc import OdbcAdapter
            a = MagicMock(spec=OdbcAdapter)
            a.connect.return_value = True
            a.is_connected.return_value = True
            return a

        monkeypatch.setattr(
            "ms_access_mcp.services.backend_selector.BackendSelector.get_adapter",
            _select
        )
        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator") as MockOrch:
            MockOrch.return_value.export_all.return_value = {"success": True, "exported": 0}
            result = runner.invoke(app, [
                "export-all",
                "--dir", str(tmp_path),
                "--db", "/tmp/test.accdb",
                "--backend", "odbc",
            ])

        assert result.exit_code == 0, result.stdout
