"""Verify CLI commands accept --backend and default to ODBC.

Tests ensure _get_adapter returns the right adapter class based on the
--backend flag.  No actual DB connections are made — we patch the adapter
constructors at their source modules.
"""
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from ms_access_mcp.cli.main import app, _get_adapter


runner = CliRunner()


class TestGetAdapterFunction:
    """Unit tests for the _get_adapter helper."""

    def test_default_backend_is_odbc(self):
        """_get_adapter() with no backend arg returns OdbcAdapter."""
        with patch("ms_access_mcp.adapters.odbc.OdbcAdapter") as MockOdbc:
            MockOdbc.return_value.connect.return_value = True
            adapter = _get_adapter("/tmp/test.accdb")

        MockOdbc.assert_called_once()
        assert adapter is MockOdbc.return_value

    def test_backend_odbc_explicit(self):
        """_get_adapter(..., backend='odbc') returns OdbcAdapter."""
        with patch("ms_access_mcp.adapters.odbc.OdbcAdapter") as MockOdbc:
            MockOdbc.return_value.connect.return_value = True
            adapter = _get_adapter("/tmp/test.accdb", backend="odbc")

        MockOdbc.assert_called_once()
        assert adapter is MockOdbc.return_value

    def test_backend_com(self):
        """_get_adapter(..., backend='com') returns WinComAdapter."""
        with patch("ms_access_mcp.adapters.wincom.WinComAdapter") as MockCom:
            MockCom.return_value.connect.return_value = True
            adapter = _get_adapter("/tmp/test.accdb", backend="com")

        MockCom.assert_called_once()
        assert adapter is MockCom.return_value

    def test_backend_com_does_not_import_odbc(self):
        """When backend='com', OdbcAdapter is not imported."""
        with patch("ms_access_mcp.adapters.wincom.WinComAdapter") as MockCom:
            MockCom.return_value.connect.return_value = True
            with patch("ms_access_mcp.adapters.odbc.OdbcAdapter") as MockOdbc:
                _get_adapter("/tmp/test.accdb", backend="com")

        MockOdbc.assert_not_called()


class TestCliExportAllBackend:
    """Verify export-all passes --backend through to _get_adapter."""

    def test_export_all_default_uses_odbc(self, tmp_path):
        """export-all without --backend creates OdbcAdapter."""
        mock_adapter = MagicMock()
        mock_adapter.is_connected.return_value = True
        mock_adapter.connect.return_value = True

        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator") as MockOrch:
            MockOrch.return_value.export_all.return_value = {"success": True, "exported": 0}
            with patch("ms_access_mcp.adapters.odbc.OdbcAdapter") as MockOdbc:
                MockOdbc.return_value = mock_adapter
                result = runner.invoke(app, [
                    "export-all",
                    "--dir", str(tmp_path),
                    "--db", "/tmp/test.accdb",
                ])

        assert result.exit_code == 0, result.stdout
        MockOdbc.assert_called_once()

    def test_export_all_com_flag_uses_com(self, tmp_path):
        """export-all --backend com creates WinComAdapter."""
        mock_adapter = MagicMock()
        mock_adapter.is_connected.return_value = True
        mock_adapter.connect.return_value = True

        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator") as MockOrch:
            MockOrch.return_value.export_all.return_value = {"success": True, "exported": 0}
            with patch("ms_access_mcp.adapters.wincom.WinComAdapter") as MockCom:
                MockCom.return_value = mock_adapter
                result = runner.invoke(app, [
                    "export-all",
                    "--dir", str(tmp_path),
                    "--db", "/tmp/test.accdb",
                    "--backend", "com",
                ])

        assert result.exit_code == 0, result.stdout
        MockCom.assert_called_once()


class TestCliCompareVersioningBackend:
    """Verify compare-versioning passes --backend through."""

    def test_compare_default_uses_odbc(self, tmp_path):
        """compare-versioning without --backend creates OdbcAdapter."""
        mock_adapter = MagicMock()
        mock_adapter.is_connected.return_value = True
        mock_adapter.connect.return_value = True

        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator") as MockOrch:
            MockOrch.return_value.compare.return_value = {
                "success": True, "new": [], "missing": [], "changed": [], "unchanged": []
            }
            with patch("ms_access_mcp.adapters.odbc.OdbcAdapter") as MockOdbc:
                MockOdbc.return_value = mock_adapter
                result = runner.invoke(app, [
                    "compare-versioning",
                    "--dir", str(tmp_path),
                    "--db", "/tmp/test.accdb",
                ])

        assert result.exit_code == 0, result.stdout
        MockOdbc.assert_called_once()

    def test_compare_com_flag_uses_com(self, tmp_path):
        """compare-versioning --backend com creates WinComAdapter."""
        mock_adapter = MagicMock()
        mock_adapter.is_connected.return_value = True
        mock_adapter.connect.return_value = True

        with patch("ms_access_mcp.orchestrators.versioning.VersioningOrchestrator") as MockOrch:
            MockOrch.return_value.compare.return_value = {
                "success": True, "new": [], "missing": [], "changed": [], "unchanged": []
            }
            with patch("ms_access_mcp.adapters.wincom.WinComAdapter") as MockCom:
                MockCom.return_value = mock_adapter
                result = runner.invoke(app, [
                    "compare-versioning",
                    "--dir", str(tmp_path),
                    "--db", "/tmp/test.accdb",
                    "--backend", "com",
                ])

        assert result.exit_code == 0, result.stdout
        MockCom.assert_called_once()


class TestCliExportVbaBackend:
    """Verify export-vba passes --backend through."""

    def test_export_vba_com_flag(self, tmp_path):
        """export-vba --backend com creates WinComAdapter."""
        mock_adapter = MagicMock()
        mock_adapter.connect.return_value = True
        mock_adapter.export_module_to_text.return_value = "Sub Test()\nEnd Sub"

        with patch("ms_access_mcp.adapters.wincom.WinComAdapter") as MockCom:
            MockCom.return_value = mock_adapter
            result = runner.invoke(app, [
                "export-vba", "Module1",
                "--db", "/tmp/test.accdb",
                "--backend", "com",
            ])

        assert result.exit_code == 0, result.stdout
        MockCom.assert_called_once()
