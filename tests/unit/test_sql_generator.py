"""Unit tests for JetSqlGenerator."""

from ms_access_mcp.services.sql_generator import JetSqlGenerator
from ms_access_mcp.models.database import TableInfo, FieldInfo, RelationshipInfo, ForeignKeyInfo


class TestJetSqlGenerator:
    """Test suite for JetSqlGenerator."""

    def test_foreign_key_info_model(self):
        """1.1 RED: ForeignKeyInfo model should exist."""
        fk = ForeignKeyInfo(
            name="FK_Orders_Customers",
            columns=["CustomerID"],
            foreign_table="Customers",
            foreign_columns=["ID"],
        )
        assert fk.name == "FK_Orders_Customers"
        assert fk.columns == ["CustomerID"]
        assert fk.foreign_table == "Customers"
        assert fk.foreign_columns == ["ID"]


class TestJetSqlGeneratorTypeMapping:
    """Test type mapping from Access DAO types to Jet SQL."""

    def test_map_text_to_varchar(self):
        """1.3 RED: Text field maps to VARCHAR with size."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Name", type="Text", size=100)
        assert gen._map_type(field) == "VARCHAR(100)"

    def test_map_text_no_size_defaults_to_255(self):
        """1.3 RED: Text field with no size defaults to VARCHAR(255)."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Name", type="Text", size=0)
        assert gen._map_type(field) == "VARCHAR(255)"

    def test_map_long_integer_to_long(self):
        """1.3 RED: Long Integer maps to LONG."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Quantity", type="Long Integer", size=0)
        assert gen._map_type(field) == "LONG"

    def test_map_integer_to_short(self):
        """1.3 RED: Integer maps to SHORT."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Status", type="Integer", size=0)
        assert gen._map_type(field) == "SHORT"

    def test_map_byte_to_byte(self):
        """1.3 RED: Byte maps to BYTE."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Flags", type="Byte", size=0)
        assert gen._map_type(field) == "BYTE"

    def test_map_boolean_to_yesno(self):
        """1.3 RED: Boolean maps to YESNO."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Active", type="Boolean", size=0)
        assert gen._map_type(field) == "YESNO"

    def test_map_datetime_to_datetime(self):
        """1.3 RED: Date/Time maps to DATETIME."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Created", type="Date/Time", size=0)
        assert gen._map_type(field) == "DATETIME"

    def test_map_currency_to_currency(self):
        """1.3 RED: Currency maps to CURRENCY."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Price", type="Currency", size=0)
        assert gen._map_type(field) == "CURRENCY"

    def test_map_counter_to_autoincrement(self):
        """1.3 RED: Counter (AutoNumber) maps to AUTOINCREMENT."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="ID", type="Counter", size=0)
        assert gen._map_type(field) == "AUTOINCREMENT"

    def test_map_single_to_single(self):
        """1.3 RED: Single maps to SINGLE."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Ratio", type="Single", size=0)
        assert gen._map_type(field) == "SINGLE"

    def test_map_double_to_double(self):
        """1.3 RED: Double maps to DOUBLE."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Value", type="Double", size=0)
        assert gen._map_type(field) == "DOUBLE"

    def test_map_decimal_to_decimal(self):
        """1.3 RED: Decimal maps to DECIMAL."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Amount", type="Decimal", size=0)
        assert gen._map_type(field) == "DECIMAL"

    def test_map_ole_object_to_longbinary(self):
        """1.3 RED: OLE Object maps to LONGBINARY."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Data", type="OLE Object", size=0)
        assert gen._map_type(field) == "LONGBINARY"

    def test_map_guid_to_char_38(self):
        """1.3 RED: GUID maps to CHAR(38)."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="UUID", type="GUID", size=0)
        assert gen._map_type(field) == "CHAR(38)"

    def test_map_binary_to_varbinary(self):
        """1.3 RED: Binary maps to VARBINARY."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Raw", type="Binary", size=0)
        assert gen._map_type(field) == "VARBINARY"

    def test_map_memo_to_memo(self):
        """1.3 RED: Memo maps to MEMO."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Notes", type="Memo", size=0)
        assert gen._map_type(field) == "MEMO"


class TestJetSqlGeneratorColumnDDL:
    """Test column DDL generation."""

    def test_column_ddl_simple(self):
        """1.4 RED: Simple column DDL."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Name", type="Text", size=100, required=False)
        ddl = gen._generate_column_ddl(field)
        assert "[Name]" in ddl
        assert "VARCHAR(100)" in ddl

    def test_column_ddl_not_null(self):
        """1.4 RED: NOT NULL column DDL."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Code", type="Text", size=50, required=True)
        ddl = gen._generate_column_ddl(field)
        assert "NOT NULL" in ddl

    def test_column_ddl_autoincrement(self):
        """1.4 RED: AUTOINCREMENT column DDL."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="ID", type="Counter", size=0, required=True)
        ddl = gen._generate_column_ddl(field)
        assert "AUTOINCREMENT" in ddl

    def test_column_ddl_default_value(self):
        """1.4 RED: Column with default value."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Status", type="Text", size=20, required=False)
        field.default_value = "Active"
        ddl = gen._generate_column_ddl(field)
        assert "DEFAULT 'Active'" in ddl

    def test_column_ddl_default_value_boolean(self):
        """1.4 RED: Boolean default value."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        field = FieldInfo(name="Active", type="Boolean", size=0, required=False)
        field.default_value = True
        ddl = gen._generate_column_ddl(field)
        assert "DEFAULT True" in ddl or "DEFAULT YESNO" in ddl or "DEFAULT -1" in ddl


class TestJetSqlGeneratorTableDDL:
    """Test table DDL generation."""

    def test_generate_create_table(self):
        """1.5 RED: Generate CREATE TABLE statement."""
        table = TableInfo(
            name="Customers",
            fields=[
                FieldInfo(name="ID", type="Counter", size=0, required=True),
                FieldInfo(name="Name", type="Text", size=100, required=False),
            ],
        )
        gen = JetSqlGenerator(tables=[table], relationships=[], foreign_keys=[])
        statements = gen.generate()
        create_stmt = next((s for s in statements if "CREATE TABLE [Customers]" in s), None)
        assert create_stmt is not None

    def test_generate_table_with_pk(self):
        """1.5 RED: Generate table with PRIMARY KEY."""
        table = TableInfo(
            name="Products",
            fields=[
                FieldInfo(name="ID", type="Counter", size=0, required=True),
                FieldInfo(name="Name", type="Text", size=100, required=False),
            ],
        )
        table.primary_key = ["ID"]
        gen = JetSqlGenerator(tables=[table], relationships=[], foreign_keys=[])
        statements = gen.generate()
        pk_stmt = next((s for s in statements if "PRIMARY KEY" in s and "[ID]" in s), None)
        assert pk_stmt is not None

    def test_generate_table_with_fk(self):
        """1.5 RED: Generate table with FOREIGN KEY constraint."""
        customers = TableInfo(
            name="Customers",
            fields=[FieldInfo(name="ID", type="Counter", size=0, required=True)],
        )
        customers.primary_key = ["ID"]
        orders = TableInfo(
            name="Orders",
            fields=[
                FieldInfo(name="ID", type="Counter", size=0, required=True),
                FieldInfo(name="CustomerID", type="Long Integer", size=0, required=True),
            ],
        )
        orders.primary_key = ["ID"]
        fk = ForeignKeyInfo(
            name="FK_Orders_Customers",
            columns=["CustomerID"],
            foreign_table="Customers",
            foreign_columns=["ID"],
        )
        gen = JetSqlGenerator(
            tables=[customers, orders],
            relationships=[],
            foreign_keys=[fk],
        )
        statements = gen.generate()
        fk_stmt = next((s for s in statements if "FOREIGN KEY" in s), None)
        assert fk_stmt is not None
        assert "REFERENCES [Customers]" in fk_stmt


class TestJetSqlGeneratorTopologicalSort:
    """Test table dependency ordering."""

    def test_orders_tables_by_dependency(self):
        """1.6 RED: Parent table appears before child table."""
        customers = TableInfo(
            name="Customers",
            fields=[FieldInfo(name="ID", type="Counter", size=0, required=True)],
        )
        customers.primary_key = ["ID"]
        orders = TableInfo(
            name="Orders",
            fields=[
                FieldInfo(name="ID", type="Counter", size=0, required=True),
                FieldInfo(name="CustomerID", type="Long Integer", size=0, required=True),
            ],
        )
        orders.primary_key = ["ID"]
        fk = ForeignKeyInfo(
            name="FK_Orders_Customers",
            columns=["CustomerID"],
            foreign_table="Customers",
            foreign_columns=["ID"],
        )
        gen = JetSqlGenerator(
            tables=[orders, customers],  # intentionally reversed
            relationships=[],
            foreign_keys=[fk],
        )
        statements = gen.generate()
        cust_idx = next(i for i, s in enumerate(statements) if "CREATE TABLE [Customers]" in s)
        ord_idx = next(i for i, s in enumerate(statements) if "CREATE TABLE [Orders]" in s)
        assert cust_idx < ord_idx, "Customers should be created before Orders"

    def test_cycle_detection_fallback(self):
        """1.6 RED: Cycle detection falls back to original order."""
        # Create a circular reference scenario
        table_a = TableInfo(
            name="TableA",
            fields=[FieldInfo(name="ID", type="Counter", size=0, required=True)],
        )
        table_a.primary_key = ["ID"]
        table_b = TableInfo(
            name="TableB",
            fields=[
                FieldInfo(name="ID", type="Counter", size=0, required=True),
                FieldInfo(name="AID", type="Long Integer", size=0, required=True),
            ],
        )
        table_b.primary_key = ["ID"]
        fk_b_to_a = ForeignKeyInfo(
            name="FK_B_to_A",
            columns=["AID"],
            foreign_table="TableA",
            foreign_columns=["ID"],
        )
        fk_a_to_b = ForeignKeyInfo(
            name="FK_A_to_B",
            columns=["ID"],
            foreign_table="TableB",
            foreign_columns=["ID"],
        )
        gen = JetSqlGenerator(
            tables=[table_a, table_b],
            relationships=[],
            foreign_keys=[fk_b_to_a, fk_a_to_b],
        )
        # Should not raise, should fall back to original order
        statements = gen.generate()
        assert len(statements) == 2


class TestJetSqlGeneratorGenerate:
    """Test the main generate() method."""

    def test_generate_returns_list_of_statements(self):
        """1.2 RED: generate() returns list of SQL strings."""
        table = TableInfo(
            name="Test",
            fields=[FieldInfo(name="ID", type="Counter", size=0, required=True)],
        )
        gen = JetSqlGenerator(tables=[table], relationships=[], foreign_keys=[])
        result = gen.generate()
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(s, str) for s in result)

    def test_generate_empty_schema(self):
        """1.2 RED: generate() with empty schema returns empty list."""
        gen = JetSqlGenerator(tables=[], relationships=[], foreign_keys=[])
        result = gen.generate()
        assert result == []