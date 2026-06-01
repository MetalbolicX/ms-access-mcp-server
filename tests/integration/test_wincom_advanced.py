"""COM integration tests for WinComAdapter linked tables, schema introspection, and launch/close.

Tests get_linked_tables, create_linked_table, refresh_linked_table, unlink_table,
get_table_schema_plan, generate_sql, get_object_metadata, launch_access, close_access.
"""

import shutil
import sys
import tempfile

import pytest

from tests.integration.helpers import (
    skip_unless_windows,
    skip_unless_pywin32,
    skip_unless_db,
    TEST_DB,
)

pytestmark = [
    pytest.mark.com_integration,
    skip_unless_windows,
    skip_unless_pywin32,
    skip_unless_db,
]


class TestWinComLinkedTables:
    """Linked table operations via WinComAdapter on temp DBs."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_source_db(self, path: str) -> None:
        """Create a minimal .accdb with one table via Access.Application COM."""
        import win32com.client

        access = win32com.client.Dispatch("Access.Application")
        access.Visible = False
        try:
            # NewCurrentDatabase opens the DB and returns a Database object
            db = access.NewCurrentDatabase(path)
            # CurrentDb gives us the DAO database to work with
            dao = access.CurrentDb()
            tbl = dao.CreateTableDef("source_table")
            tbl.Fields.Append(tbl.CreateField("ID", 4))  # 4 = dbLong
            tbl.Fields.Append(tbl.CreateField("Name", 10, 255))  # 10 = dbText
            dao.TableDefs.Append(tbl)
        finally:
            try:
                access.Quit(2)  # acQuitPromptNever = 2
            except Exception:
                pass

    def test_get_linked_tables_returns_proper_shape(self):
        """get_linked_tables returns dict with success=True and linked_tables list."""
        result = self.adapter.get_linked_tables()
        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is True
        assert "linked_tables" in result
        assert isinstance(result["linked_tables"], list)

    def test_create_and_refresh_linked_table(self):
        """Create a linked table pointing to a second temp .accdb, then refresh it."""
        # Create the source database
        with tempfile.NamedTemporaryFile(suffix=".accdb", delete=False) as f:
            source_path = f.name
        try:
            self._create_source_db(source_path)

            # Build ODBC connect string for the source
            connect_str = f"Access;DATABASE={source_path}"

            # Create linked table
            result = self.adapter.create_linked_table(
                "linked_test", "source_table", connect_str
            )
            assert result["success"] is True

            # Refresh the link
            refresh_result = self.adapter.refresh_linked_table("linked_test")
            assert refresh_result["success"] is True

            # Verify it appears in linked tables list
            linked = self.adapter.get_linked_tables()
            assert linked["success"] is True
            names = [t["name"] for t in linked["linked_tables"]]
            assert "linked_test" in names
        finally:
            if sys.platform == "win32":
                try:
                    import os

                    os.unlink(source_path)
                except Exception:
                    pass

    def test_unlink_table(self):
        """Create a linked table then unlink it."""
        with tempfile.NamedTemporaryFile(suffix=".accdb", delete=False) as f:
            source_path = f.name
        try:
            self._create_source_db(source_path)
            connect_str = f"Access;DATABASE={source_path}"

            create_result = self.adapter.create_linked_table(
                "to_unlink", "source_table", connect_str
            )
            assert create_result["success"] is True

            unlink_result = self.adapter.unlink_table("to_unlink")
            assert unlink_result["success"] is True

            # Verify it's gone
            linked = self.adapter.get_linked_tables()
            names = [t["name"] for t in linked["linked_tables"]]
            assert "to_unlink" not in names
        finally:
            if sys.platform == "win32":
                try:
                    import os

                    os.unlink(source_path)
                except Exception:
                    pass

    def test_unlink_nonexistent_returns_error(self):
        """Unlink a table that doesn't exist returns success=False."""
        result = self.adapter.unlink_table("nonexistent_link_xyz")
        assert result["success"] is False
        assert "error" in result

    def test_create_linked_table_bad_connect_string(self):
        """Create linked table with a bad connect string returns error."""
        result = self.adapter.create_linked_table(
            "bad_link", "nonexistent_table", "ODBC;DSN=BAD_DSN_XYZ"
        )
        assert result["success"] is False
        assert "error" in result


class TestWinComSchema:
    """Schema introspection via WinComAdapter on temp DB."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()
        assert self.adapter.connect(self.db_path), "Connect failed"

    def teardown_method(self):
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_table_schema_plan_returns_tuple(self):
        """get_table_schema_plan returns tuple (list[TableSchema], UnknownMetadata)."""
        result = self.adapter.get_table_schema_plan()
        assert isinstance(result, tuple)
        assert len(result) == 2
        tables, unknown = result
        assert isinstance(tables, list)
        # Check first table structure if any
        if tables:
            t = tables[0]
            assert hasattr(t, "name")
            assert hasattr(t, "columns")
            assert hasattr(t, "primary_key")
            assert hasattr(t, "foreign_keys")
            assert hasattr(t, "indexes")
        # unknown should have boolean flags
        assert hasattr(unknown, "primary_keys")
        assert hasattr(unknown, "foreign_keys")
        assert hasattr(unknown, "defaults")
        assert hasattr(unknown, "indexes")

    def test_generate_sql_writes_file(self):
        """generate_sql writes DDL to a temp file and returns success."""
        with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as f:
            output_path = f.name

        result = self.adapter.generate_sql(output_path)
        assert result["success"] is True
        assert result["path"] == output_path
        assert "statements" in result
        assert "tables" in result
        assert isinstance(result["tables"], list)

        # File should exist and have content
        import os

        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0
        os.unlink(output_path)

    def test_get_object_metadata_on_table(self):
        """get_object_metadata returns dict for an existing table."""
        # Use 'customers' if it exists in fixture
        result = self.adapter.get_object_metadata("customers")
        if result:
            assert "name" in result
            assert "type" in result
            assert result["type"] == "table"

    def test_get_object_metadata_on_form(self):
        """get_object_metadata returns dict for an existing form."""
        # Use 'frmMain' or similar if it exists
        result = self.adapter.get_object_metadata("frmMain")
        if result:
            assert "name" in result
            assert "type" in result
            assert result["type"] in ("form", "table")


class TestWinComLaunchClose:
    """Access launch/close lifecycle — run last, isolated since they touch singleton."""

    def setup_method(self):
        from ms_access_mcp.adapters.wincom import WinComAdapter

        self.tmpdir = tempfile.mkdtemp()
        self.db_path = shutil.copy2(TEST_DB, self.tmpdir)
        self.adapter = WinComAdapter()

    def teardown_method(self):
        try:
            self.adapter.close_access()
        except Exception:
            pass
        self.adapter.disconnect()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_launch_access_does_not_raise(self):
        """launch_access(visible=False) starts Access without raising."""
        # launch_access may start dispatcher internally
        self.adapter.connect(self.db_path)
        # Should not raise
        self.adapter.launch_access(visible=False)

    def test_close_access_does_not_raise(self):
        """close_access closes Access without raising."""
        self.adapter.connect(self.db_path)
        self.adapter.launch_access(visible=False)
        # Should not raise
        self.adapter.close_access()