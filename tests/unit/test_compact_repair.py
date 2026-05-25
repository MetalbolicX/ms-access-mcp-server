import pytest
from unittest.mock import MagicMock, patch
from ms_access_mcp.adapters.base import AccessAdapter
from ms_access_mcp.adapters.odbc import OdbcAdapter
from ms_access_mcp.adapters.wincom import WinComAdapter


class TestOdbcAdapterCompactRepair:
    def test_compact_repair_odbc_stub(self):
        adapter = OdbcAdapter()
        result = adapter.compact_repair(
            action="compact",
            source_path="test.accdb",
            dest_path="test_compacted.accdb",
            keep_original=True
        )
        assert result["success"] is False
        assert "Not available via ODBC" in result["error"]

    def test_compact_repair_odbc_stub_repair_action(self):
        adapter = OdbcAdapter()
        result = adapter.compact_repair(
            action="repair",
            source_path="test.accdb",
            dest_path="test.accdb",
            keep_original=False
        )
        assert result["success"] is False
        assert "Not available via ODBC" in result["error"]


class TestCompactRepairInvalidAction:
    def test_compact_repair_invalid_action_returns_error(self):
        adapter = OdbcAdapter()
        result = adapter.compact_repair(
            action="invalid",
            source_path="test.accdb",
            dest_path="test.accdb",
            keep_original=True
        )
        assert result["success"] is False
        assert "Invalid action" in result["error"] or "must be" in result["error"]


class TestWinComAdapterCompactRepair:
    @patch("ms_access_mcp.adapters.wincom.WinComAdapter.is_connected")
    def test_compact_repair_wincom_compact(self, mock_is_connected):
        mock_is_connected.return_value = True

        adapter = WinComAdapter()
        adapter._dispatcher = MagicMock()
        adapter._db_path = "test.accdb"
        adapter._dispatcher._access_app = MagicMock()
        adapter._dispatcher._access_app.Dao = MagicMock()

        dao_mock = MagicMock()
        adapter._dispatcher._access_app.Dao = dao_mock
        db_engine_mock = MagicMock()
        dao_mock.DBEngine = db_engine_mock

        original_size = 1024
        compacted_size = 512

        def mock_compact(source, dest):
            pass

        db_engine_mock.CompactDatabase = MagicMock(side_effect=mock_compact)

        with patch("os.path.getsize") as mock_getsize, \
             patch("os.path.exists") as mock_exists, \
             patch("os.rename") as mock_rename, \
             patch("os.unlink") as mock_unlink, \
             patch("shutil.copy2") as mock_copy2:

            mock_exists.return_value = True
            mock_getsize.side_effect = [original_size, compacted_size]

            def dispatcher_call_side_effect(fn, *args, **kwargs):
                return fn(*args, **kwargs)

            adapter._dispatcher.call = dispatcher_call_side_effect

            result = adapter.compact_repair(
                action="compact",
                source_path="test.accdb",
                dest_path="test_compacted.accdb",
                keep_original=True
            )

            assert result["success"] is True
            assert result["output_path"] == "test_compacted.accdb"
            assert "stats" in result
            assert result["stats"]["original_size"] == original_size
            assert result["stats"]["compacted_size"] == compacted_size

    @patch("ms_access_mcp.adapters.wincom.WinComAdapter.is_connected")
    def test_compact_repair_wincom_repair(self, mock_is_connected):
        mock_is_connected.return_value = True

        adapter = WinComAdapter()
        adapter._dispatcher = MagicMock()
        adapter._db_path = "test.accdb"
        adapter._dispatcher._access_app = MagicMock()

        original_size = 1024
        compacted_size = 512

        def dispatcher_call_side_effect(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        adapter._dispatcher.call = dispatcher_call_side_effect

        app_mock = MagicMock()
        adapter._dispatcher._access_app = app_mock

        with patch("os.path.getsize") as mock_getsize, \
             patch("os.path.exists") as mock_exists, \
             patch("os.rename") as mock_rename, \
             patch("os.unlink") as mock_unlink, \
             patch("os.replace") as mock_replace, \
             patch("shutil.copy2") as mock_copy2:

            mock_exists.return_value = True
            mock_getsize.side_effect = [original_size, compacted_size]

            result = adapter.compact_repair(
                action="repair",
                source_path="test.accdb",
                dest_path="test.accdb",
                keep_original=False
            )

            print(f"DEBUG repair result: {result}")
            if not result["success"]:
                print(f"DEBUG repair error: {result.get('error')}")
            assert result["success"] is True
            assert "stats" in result

    @patch("ms_access_mcp.adapters.wincom.WinComAdapter.is_connected")
    def test_compact_repair_wincom_file_not_found(self, mock_is_connected):
        mock_is_connected.return_value = True

        adapter = WinComAdapter()
        adapter._dispatcher = MagicMock()
        adapter._db_path = "test.accdb"

        def dispatcher_call_side_effect(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        adapter._dispatcher.call = dispatcher_call_side_effect

        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = False

            result = adapter.compact_repair(
                action="compact",
                source_path="nonexistent.accdb",
                dest_path="test.accdb",
                keep_original=True
            )

            assert result["success"] is False
            assert "not found" in result["error"].lower()


class TestAccessAdapterProtocol:
    def test_compact_repair_in_protocol(self):
        assert hasattr(AccessAdapter, "compact_repair")

    def test_dummy_adapter_implements_compact_repair(self):
        class DummyAdapter:
            def compact_repair(self, action: str, source_path: str, dest_path: str, keep_original: bool = True) -> dict:
                return {"success": True}

        adapter: AccessAdapter = DummyAdapter()
        result = adapter.compact_repair("compact", "source.accdb", "dest.accdb", True)
        assert result["success"] is True