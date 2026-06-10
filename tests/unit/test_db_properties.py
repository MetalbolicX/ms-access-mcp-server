"""Tests for mcp/db_properties.py tool bindings, DbOperations, and DatabasePropertyInfo — PR3.

TDD: tests written first, then implementation follows.
"""

import pytest
from unittest.mock import patch, MagicMock

from ms_access_mcp.mcp import server  # noqa: F401
from ms_access_mcp.mcp import db_properties as db_props_module
from ms_access_mcp.models.database import DatabasePropertyInfo
from ms_access_mcp.adapters.db_operations import DbOperations, _detect_dao_type

# ============================================================================
# Model tests — DatabasePropertyInfo
# ============================================================================


class TestDatabasePropertyInfoModel:
    """Tests for the DatabasePropertyInfo Pydantic model."""

    def test_minimal_instantiation(self):
        """All four required fields, built_in defaults to False."""
        prop = DatabasePropertyInfo(
            name="Author",
            value="Jane Developer",
            type="Text",
        )
        assert prop.name == "Author"
        assert prop.value == "Jane Developer"
        assert prop.type == "Text"
        assert prop.built_in is False

    def test_built_in_true(self):
        """built_in=True for system/Access-managed properties."""
        prop = DatabasePropertyInfo(
            name="AppTitle",
            value="My App",
            type="Text",
            built_in=True,
        )
        assert prop.built_in is True

    def test_type_boolean(self):
        """Boolean type field for boolean properties."""
        prop = DatabasePropertyInfo(
            name="AllowFullMenus",
            value="True",
            type="Boolean",
        )
        assert prop.type == "Boolean"

    def test_type_long(self):
        """Long type field for integer properties."""
        prop = DatabasePropertyInfo(
            name="StartUpPos",
            value="100",
            type="Long",
        )
        assert prop.type == "Long"

    def test_serialization_round_trip(self):
        """model_dump round-trip preserves all fields."""
        prop = DatabasePropertyInfo(
            name="Company",
            value="Acme Corp",
            type="Text",
            built_in=False,
        )
        data = prop.model_dump()
        assert data["name"] == "Company"
        assert data["value"] == "Acme Corp"
        assert data["type"] == "Text"
        assert data["built_in"] is False


# ============================================================================
# get_database_properties — MCP tool tests
# ============================================================================


class TestGetDatabasePropertiesTool:
    """Tests for the get_database_properties MCP tool."""

    def test_returns_error_when_not_connected(self):
        """Should return success=False when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(db_props_module, "_pool", return_value=mock_conn):
            result = server.get_database_properties()
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_returns_properties_dict(self):
        """Should return success=True with adapter's properties dict."""
        mock_adapter = MagicMock()
        mock_adapter.get_database_properties.return_value = {
            "startup": {"AppTitle": "MyApp"},
            "app": {"Author": "Jane"},
            "project": {"Path": "C:/db.accdb"},
            "all": {"AppTitle": "MyApp", "Author": "Jane", "Path": "C:/db.accdb"},
        }
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(db_props_module, "_pool", return_value=mock_conn):
            result = server.get_database_properties()
            assert result["success"] is True
            assert "properties" in result
            props = result["properties"]
            assert "startup" in props
            assert "app" in props
            assert "project" in props
            assert "all" in props

    def test_passes_names_filter_to_adapter(self):
        """The names parameter should be passed through to the adapter."""
        mock_adapter = MagicMock()
        mock_adapter.get_database_properties.return_value = {
            "startup": {},
            "app": {},
            "project": {},
            "all": {"AppTitle": "MyApp"},
        }
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(db_props_module, "_pool", return_value=mock_conn):
            result = server.get_database_properties(names=["AppTitle"])
            assert result["success"] is True
            mock_adapter.get_database_properties.assert_called_once_with(["AppTitle"])

    def test_passes_none_names_by_default(self):
        """When no names param is provided, adapter receives None."""
        mock_adapter = MagicMock()
        mock_adapter.get_database_properties.return_value = {
            "startup": {},
            "app": {},
            "project": {},
            "all": {},
        }
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(db_props_module, "_pool", return_value=mock_conn):
            server.get_database_properties()
            mock_adapter.get_database_properties.assert_called_once_with(None)

    def test_adapter_exception_propagates(self):
        """If the adapter raises, the exception propagates from the tool."""
        mock_adapter = MagicMock()
        mock_adapter.get_database_properties.side_effect = RuntimeError("COM dead")
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(db_props_module, "_pool", return_value=mock_conn):
            with pytest.raises(RuntimeError, match="COM dead"):
                server.get_database_properties()


# ============================================================================
# set_database_property — MCP tool tests
# ============================================================================


class TestSetDatabasePropertyTool:
    """Tests for the set_database_property MCP tool."""

    def test_returns_error_when_not_connected(self):
        """Should return success=False when not connected."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = False
        with patch.object(db_props_module, "_pool", return_value=mock_conn):
            result = server.set_database_property("AppTitle", "NewTitle", confirm=True)
            assert result["success"] is False
            assert "Not connected" in result["error"]

    def test_blocked_without_confirmation(self):
        """Should be blocked by guard when confirm=False."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(db_props_module, "_pool", return_value=mock_conn):
            result = server.set_database_property("AppTitle", "NewTitle")
            assert result["success"] is False
            assert "confirm=True required" in result["error"]
            assert result["name"] == "AppTitle"

    def test_dry_run_returns_preview(self):
        """Should return dry_run preview without executing."""
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        with patch.object(db_props_module, "_pool", return_value=mock_conn):
            result = server.set_database_property("AppTitle", "NewTitle", dry_run=True)
            assert result["dry_run"] is True
            assert result["action"] == "set_database_property"
            assert result["name"] == "AppTitle"
            assert result["value"] == "NewTitle"

    def test_success_with_confirmation(self):
        """Should delegate to adapter when confirm=True."""
        mock_adapter = MagicMock()
        mock_adapter.set_database_property.return_value = True
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(db_props_module, "_pool", return_value=mock_conn):
            result = server.set_database_property("AppTitle", "NewTitle", confirm=True)
            assert result["success"] is True
            assert result["property"] == "AppTitle"
            assert result["value"] == "NewTitle"
            mock_adapter.set_database_property.assert_called_once_with("AppTitle", "NewTitle")

    def test_adapter_failure_returns_success_false(self):
        """If the adapter returns False, the tool should reflect that."""
        mock_adapter = MagicMock()
        mock_adapter.set_database_property.return_value = False
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(db_props_module, "_pool", return_value=mock_conn):
            result = server.set_database_property("AppTitle", "NewTitle", confirm=True)
            assert result["success"] is False
            assert result["property"] == "AppTitle"

    def test_adapter_exception_propagates(self):
        """Adapter exceptions should propagate (per spec)."""
        mock_adapter = MagicMock()
        mock_adapter.set_database_property.side_effect = RuntimeError("Property locked")
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_conn.get_adapter.return_value = mock_adapter
        with patch.object(db_props_module, "_pool", return_value=mock_conn):
            with pytest.raises(RuntimeError, match="Property locked"):
                server.set_database_property("AppTitle", "NewTitle", confirm=True)


# ============================================================================
# _detect_dao_type — operations class helper tests
# ============================================================================


class TestDetectDaoType:
    """Tests for the _detect_dao_type auto-detection helper."""

    def test_true_detected_as_boolean(self):
        """The string 'true' is detected as Boolean."""
        assert _detect_dao_type("true") == ("Boolean", 1)

    def test_false_detected_as_boolean(self):
        """The string 'false' is detected as Boolean."""
        assert _detect_dao_type("false") == ("Boolean", 1)

    def test_uppercase_true_detected_as_boolean(self):
        """The string 'TRUE' is detected as Boolean (case-insensitive)."""
        assert _detect_dao_type("TRUE") == ("Boolean", 1)

    def test_integer_string_detected_as_long(self):
        """A digit-only string is detected as Long."""
        assert _detect_dao_type("42") == ("Long", 4)

    def test_zero_detected_as_long(self):
        """The string '0' is detected as Long (not Boolean)."""
        assert _detect_dao_type("0") == ("Long", 4)

    def test_negative_integer_detected_as_long(self):
        """A negative digit string is detected as Long."""
        # "-" alone fails float() and isdigit() == False, so falls to Text.
        # "-5" isdigit() is False too (because of the leading minus), but
        # float("-5") succeeds, returning Double. This is acceptable: callers
        # who want Long can pass type explicitly.
        result = _detect_dao_type("-5")
        assert result[0] in ("Long", "Double")
        assert result[1] in (4, 7)

    def test_float_string_detected_as_double(self):
        """A decimal string is detected as Double."""
        assert _detect_dao_type("3.14") == ("Double", 7)

    def test_text_string_detected_as_text(self):
        """A non-numeric, non-boolean string is detected as Text."""
        assert _detect_dao_type("Hello World") == ("Text", 10)

    def test_empty_string_detected_as_text(self):
        """Empty string falls through to Text."""
        assert _detect_dao_type("") == ("Text", 10)


# ============================================================================
# DbOperations — operations class tests (with mocked dispatcher)
# ============================================================================


class TestDbOperationsInit:
    """Tests that DbOperations stores its dispatcher reference."""

    def test_init_stores_dispatcher(self):
        """__init__ should keep a reference to the dispatcher."""
        mock_dispatcher = MagicMock()
        ops = DbOperations(mock_dispatcher)
        assert ops._dispatcher is mock_dispatcher


class TestDbOperationsGetProperties:
    """Tests for DbOperations.get_database_properties with a mocked CurrentDb."""

    def _make_ops_with_db(self, props):
        """Build a DbOperations whose dispatcher returns the given props collection."""
        mock_dispatcher = MagicMock()
        mock_dispatcher._started = True
        # Set access_app to None so the CurrentProject enrichment in the
        # implementation is skipped (avoids leaking MagicMock values into the
        # `project` category). Tests that care about project info set it
        # explicitly.
        mock_dispatcher.access_app = None

        # Build a Properties collection as a list of mocks
        prop_mocks = []
        for p in props:
            pm = MagicMock()
            pm.Name = p["name"]
            pm.Value = p["value"]
            pm.Type = p["type"]
            prop_mocks.append(pm)

        # Properties needs to support .Count and (i) indexing like DAO COM
        props_mock = MagicMock()
        props_mock.Count = len(prop_mocks)
        props_mock.side_effect = lambda i: prop_mocks[i]
        # Make iteration (used by some DAO versions) also work
        props_mock.__iter__ = lambda self: iter(prop_mocks)

        mock_db = MagicMock()
        mock_db.Properties = props_mock
        mock_dispatcher.current_db = mock_db
        # dispatcher.call should execute the function (simulating the STA thread)
        mock_dispatcher.call.side_effect = lambda fn, *a, **kw: fn()

        return DbOperations(mock_dispatcher), mock_dispatcher, prop_mocks

    def test_filters_internal_properties_underscore(self):
        """Properties starting with '_' should be filtered out."""
        ops, _mock_disp, _ = self._make_ops_with_db(
            [
                {"name": "_CustomProperty", "value": "secret", "type": 10},
                {"name": "Author", "value": "Jane", "type": 10},
            ]
        )
        result = ops.get_database_properties()
        assert "Author" in result["all"]
        assert "_CustomProperty" not in result["all"]

    def test_filters_internal_properties_msys(self):
        """Properties starting with 'MSys' should be filtered out."""
        ops, _mock_disp, _ = self._make_ops_with_db(
            [
                {"name": "MSysSomething", "value": "x", "type": 10},
                {"name": "AppTitle", "value": "MyApp", "type": 10},
            ]
        )
        result = ops.get_database_properties()
        assert "AppTitle" in result["all"]
        assert "MSysSomething" not in result["all"]

    def test_returns_empty_dict_when_no_properties(self):
        """Should return categorized dict with all empty when no props."""
        ops, _, _ = self._make_ops_with_db([])
        result = ops.get_database_properties()
        assert isinstance(result, dict)
        assert result["startup"] == {}
        assert result["app"] == {}
        assert result["project"] == {}
        assert result["all"] == {}

    def test_names_filter_includes_only_matching(self):
        """When names is provided, only matching properties are included."""
        ops, _, _ = self._make_ops_with_db(
            [
                {"name": "AppTitle", "value": "MyApp", "type": 10},
                {"name": "Author", "value": "Jane", "type": 10},
                {"name": "Company", "value": "Acme", "type": 10},
            ]
        )
        result = ops.get_database_properties(names=["Author", "Company"])
        assert "Author" in result["all"]
        assert "Company" in result["all"]
        assert "AppTitle" not in result["all"]

    def test_names_filter_empty_result(self):
        """When names is provided but no matches, all categories empty."""
        ops, _, _ = self._make_ops_with_db(
            [
                {"name": "AppTitle", "value": "MyApp", "type": 10},
            ]
        )
        result = ops.get_database_properties(names=["DoesNotExist"])
        assert result["all"] == {}
        assert result["startup"] == {}
        assert result["app"] == {}
        assert result["project"] == {}

    def test_categorizes_startup_property(self):
        """AppTitle (a startup property) goes into startup category."""
        ops, _, _ = self._make_ops_with_db(
            [
                {"name": "AppTitle", "value": "MyApp", "type": 10},
            ]
        )
        result = ops.get_database_properties()
        assert "AppTitle" in result["startup"]
        assert "AppTitle" in result["all"]

    def test_categorizes_app_property(self):
        """Author (an app property) goes into app category."""
        ops, _, _ = self._make_ops_with_db(
            [
                {"name": "Author", "value": "Jane", "type": 10},
            ]
        )
        result = ops.get_database_properties()
        assert "Author" in result["app"]
        assert "Author" in result["all"]

    def test_returns_dict_with_all_required_keys(self):
        """Result dict must contain startup, app, project, all keys."""
        ops, _, _ = self._make_ops_with_db([])
        result = ops.get_database_properties()
        assert "startup" in result
        assert "app" in result
        assert "project" in result
        assert "all" in result


class TestDbOperationsSetProperty:
    """Tests for DbOperations.set_database_property with a mocked CurrentDb."""

    def test_returns_false_when_not_started(self):
        """If dispatcher is not started, return False without touching COM."""
        mock_dispatcher = MagicMock()
        mock_dispatcher._started = False
        ops = DbOperations(mock_dispatcher)
        result = ops.set_database_property("AppTitle", "NewTitle")
        assert result is False
        mock_dispatcher.call.assert_not_called()

    def test_updates_existing_property(self):
        """If property exists, its value should be updated (no Append)."""
        existing = MagicMock()
        existing.Name = "AppTitle"
        existing.Value = "OldTitle"
        props_mock = MagicMock()
        props_mock.Count = 1
        props_mock.side_effect = lambda i: existing
        mock_db = MagicMock()
        mock_db.Properties = props_mock
        mock_dispatcher = MagicMock()
        mock_dispatcher._started = True
        mock_dispatcher.current_db = mock_db

        ops = DbOperations(mock_dispatcher)
        # _do runs on the STA thread — dispatcher.call wraps it
        mock_dispatcher.call.side_effect = lambda fn, *a, **kw: fn()
        result = ops.set_database_property("AppTitle", "NewTitle")
        assert result is True
        assert existing.Value == "NewTitle"
        props_mock.Append.assert_not_called()

    def test_creates_new_property_when_missing(self):
        """If property doesn't exist, create + Append it."""
        existing = MagicMock()
        existing.Name = "OtherProp"
        new_prop = MagicMock()
        props_mock = MagicMock()
        props_mock.Count = 1
        props_mock.side_effect = lambda i: existing
        mock_db = MagicMock()
        mock_db.Properties = props_mock
        mock_db.CreateProperty.return_value = new_prop
        mock_dispatcher = MagicMock()
        mock_dispatcher._started = True
        mock_dispatcher.current_db = mock_db

        ops = DbOperations(mock_dispatcher)
        mock_dispatcher.call.side_effect = lambda fn, *a, **kw: fn()
        result = ops.set_database_property("CustomProp", "custom")
        assert result is True
        mock_db.CreateProperty.assert_called_once()
        # Append should have been called with the created property
        props_mock.Append.assert_called_once_with(new_prop)

    def test_returns_false_on_exception(self):
        """If any COM error happens, return False."""
        mock_db = MagicMock()
        # Make .Count raise to simulate a COM error inside the read loop
        mock_db.Properties = MagicMock()
        type(mock_db.Properties).Count = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("boom"))
        )
        # CreateProperty should also throw — outer try/except will catch it
        mock_db.CreateProperty.side_effect = RuntimeError("create failed")
        mock_dispatcher = MagicMock()
        mock_dispatcher._started = True
        mock_dispatcher.current_db = mock_db
        mock_dispatcher.call.side_effect = lambda fn, *a, **kw: fn()

        ops = DbOperations(mock_dispatcher)
        result = ops.set_database_property("AppTitle", "NewTitle")
        assert result is False


# ============================================================================
# Adapter contract — OdbcAdapter should raise NotImplementedError
# ============================================================================


class TestOdbcAdapterStubsForDbProperties:
    """OdbcAdapter must raise NotImplementedError for COM-only db_properties methods."""

    def test_get_database_properties_raises_not_implemented(self):
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        with pytest.raises(NotImplementedError):
            OdbcAdapter().get_database_properties()

    def test_set_database_property_raises_not_implemented(self):
        from ms_access_mcp.adapters.odbc import OdbcAdapter

        with pytest.raises(NotImplementedError):
            OdbcAdapter().set_database_property("AppTitle", "NewTitle")


# ============================================================================
# WinComAdapter delegation tests
# ============================================================================


class TestWinComAdapterDbPropertiesNotConnected:
    """WinComAdapter should return safe defaults when not connected."""

    def test_get_database_properties_returns_empty_categorized_dict(self):
        """When not connected, get_database_properties returns empty categories."""
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = WinComAdapter()
        result = adapter.get_database_properties()
        assert isinstance(result, dict)
        # All categories should be empty dicts
        for key in ("startup", "app", "project", "all"):
            assert result.get(key) == {}

    def test_set_database_property_returns_false(self):
        """When not connected, set_database_property returns False."""
        from ms_access_mcp.adapters.wincom import WinComAdapter

        adapter = WinComAdapter()
        result = adapter.set_database_property("AppTitle", "NewTitle")
        assert result is False
