"""
Integration tests against the real Access database at:
D:\JMS\Limbo\excel-and-sql-book\data\db\helper.accdb

Requires Windows with Access installed and pywin32.
Run with: pytest tests/integration/test_real_adapter.py -v
"""

import pytest
import os
import tempfile
from ms_access_mcp.adapters.wincom import WinComAdapter


# Path to the real test database
TEST_DB = r"D:\JMS\Limbo\excel-and-sql-book\data\db\helper.accdb"


class TestWinComAdapterWithRealDb:
    """Test WinComAdapter against the real helper.accdb database."""

    def setup_method(self):
        self.adapter = WinComAdapter()
        assert self.adapter.connect(TEST_DB), f"Failed to connect to {TEST_DB}"
        assert self.adapter.is_connected()

    def teardown_method(self):
        self.adapter.disconnect()
        assert not self.adapter.is_connected()

    def test_get_tables_returns_real_tables(self):
        tables = self.adapter.get_tables()
        table_names = [t.name for t in tables]
        assert "customers" in table_names
        assert "orders" in table_names
        assert "products" in table_names
        assert len(tables) >= 9  # We saw 9 tables in the DB

    def test_get_tables_includes_fields(self):
        tables = self.adapter.get_tables()
        customers = next(t for t in tables if t.name == "customers")
        assert len(customers.fields) > 0
        field_names = [f.name for f in customers.fields]
        assert any("name" in n.lower() for n in field_names)

    def test_execute_query_customers(self):
        rows = self.adapter.execute_query("SELECT COUNT(*) as cnt FROM [customers]")
        assert len(rows) == 1
        assert "cnt" in rows[0]

    def test_get_relationships_finds_real_relations(self):
        rels = self.adapter.get_relationships()
        # Should find at least the non-system relation
        non_system = [r for r in rels if not r.name.startswith("MSys") and not r.name.startswith("~")]
        assert len(non_system) >= 1, f"Expected at least 1 real relation, got: {[r.name for r in rels]}"

    def test_get_forms(self):
        forms = self.adapter.get_forms()
        form_names = [f.name for f in forms]
        assert "frmDsnlessConnection" in form_names

    def test_get_modules(self):
        modules = self.adapter.get_modules()
        module_names = [m.name for m in modules]
        assert "mod_funcs" in module_names
        assert "mod_data_types" in module_names

    def test_get_vba_code_returns_content(self):
        code = self.adapter.get_vba_code("mod_funcs")
        assert len(code) > 0
        assert "Function" in code or "Sub" in code or "Option" in code

    def test_export_module_to_text(self):
        content = self.adapter.export_module_to_text("mod_funcs")
        assert len(content) > 0
        assert "Function" in content or "Sub" in content or "Option" in content

    def test_export_form_to_text(self):
        content = self.adapter.export_form_to_text("frmDsnlessConnection")
        assert len(content) > 0

    def test_export_macro_to_text_not_found(self):
        # Non-existent macro
        content = self.adapter.export_macro_to_text("NonExistentMacro")
        assert content == ""

    def test_execute_sql_script_create_and_drop(self):
        """Test creating a temp table and dropping it."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False, encoding='utf-8') as f:
            f.write("CREATE TABLE TestTemp (ID INTEGER PRIMARY KEY, Name TEXT(50));")
            f.write("DROP TABLE TestTemp;")
            script_path = f.name

        try:
            result = self.adapter.execute_sql_script(script_path)
            assert result["success"] is True, f"Expected success, got: {result}"
            assert result["statements_executed"] == 2
        finally:
            os.unlink(script_path)

    def test_execute_sql_script_file_not_found(self):
        result = self.adapter.execute_sql_script(r"C:\nonexistent\path\test.sql")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_execute_sql_script_invalid_sql(self):
        """Test that invalid SQL triggers rollback."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False, encoding='utf-8') as f:
            f.write("INSERT INTO nonexistent_table VALUES (1);")
            script_path = f.name

        try:
            result = self.adapter.execute_sql_script(script_path)
            assert result["success"] is False
            assert "statements_executed" in result
            assert result["statements_executed"] == 0
        finally:
            os.unlink(script_path)

    def test_export_all_versioning_creates_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.adapter.export_all_versioning(tmpdir)
            assert result["success"] is True, f"Expected success, got: {result}"
            assert result["file_count"] >= 1
            assert len(result["exported"]["modules"]) >= 2  # mod_funcs, mod_data_types

            # Check modules were actually written
            modules_dir = os.path.join(tmpdir, "modules")
            assert os.path.exists(modules_dir)
            files = os.listdir(modules_dir)
            assert len(files) >= 2

    def test_get_tables_system_tables(self):
        system = self.adapter.get_system_tables()
        # May be empty if no MSys tables accessible
        assert isinstance(system, list)

    def test_get_object_metadata(self):
        meta = self.adapter.get_object_metadata("customers")
        assert isinstance(meta, dict)

    def test_form_exists(self):
        assert self.adapter.form_exists("frmDsnlessConnection") is True
        assert self.adapter.form_exists("NonExistentForm") is False


@pytest.mark.skipif(
    not os.path.exists(TEST_DB),
    reason=f"Test database not found at {TEST_DB}"
)
class TestSchemaServiceWithRealDb:
    """Test SchemaService delegates correctly with real adapter."""

    def setup_method(self):
        from ms_access_mcp.services.schema import SchemaService
        self.adapter = WinComAdapter()
        assert self.adapter.connect(TEST_DB)
        self.service = SchemaService(self.adapter)
        self.service.set_adapter(self.adapter)

    def teardown_method(self):
        self.adapter.disconnect()

    def test_get_tables(self):
        tables = self.service.get_tables()
        assert len(tables) >= 9

    def test_get_relationships(self):
        rels = self.service.get_relationships()
        non_system = [r for r in rels if not r.name.startswith("MSys")]
        assert len(non_system) >= 1

    def test_export_module_to_text(self):
        content = self.service.export_module_to_text("mod_funcs")
        assert len(content) > 0

    def test_execute_sql_script(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False, encoding='utf-8') as f:
            f.write("SELECT 1 AS test;")
            script_path = f.name
        try:
            result = self.service.execute_sql_script(script_path)
            assert result["success"] is True
            assert result["statements_executed"] == 1
        finally:
            os.unlink(script_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
