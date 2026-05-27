"""Contract/property-style tests for schema mapping and SQL generation."""

from ms_access_mcp.models.database import FieldInfo, ForeignKeyInfo, TableInfo
from ms_access_mcp.models.migration import ColumnSchema, ForeignKeySchema, IndexSchema, TableSchema
from ms_access_mcp.services.schema_mapper import SchemaMapper
from ms_access_mcp.services.sql_generator import JetSqlGenerator


class TestSchemaMapperContracts:
    def test_map_column_preserves_core_flags(self):
        mapper = SchemaMapper()
        cases = [
            ColumnSchema(name="A", source_type="Text", max_length=20, allow_null=True, is_autoincrement=False),
            ColumnSchema(name="B", source_type="Long Integer", allow_null=False, is_autoincrement=False),
            ColumnSchema(name="C", source_type="Counter", allow_null=False, is_autoincrement=True),
        ]

        for target in ["postgres", "mysql", "mariadb", "sqlite", "sqlserver"]:
            for col in cases:
                mapped = mapper.map_column(col, target)
                assert mapped.name == col.name
                assert mapped.allow_null == col.allow_null
                assert mapped.is_autoincrement == col.is_autoincrement
                assert isinstance(mapped.target_type, str)
                assert mapped.target_type.strip() != ""

    def test_map_column_unknown_target_falls_back_to_postgres_mapping(self):
        mapper = SchemaMapper()
        col = ColumnSchema(name="Name", source_type="Text", max_length=30, allow_null=True, is_autoincrement=False)
        mapped = mapper.map_column(col, "unknown-db")
        assert mapped.target_type == "VARCHAR(30)"

    def test_map_column_unknown_source_type_falls_back_to_text(self):
        mapper = SchemaMapper()
        col = ColumnSchema(name="Mystery", source_type="UnmappedType", allow_null=True, is_autoincrement=False)
        mapped = mapper.map_column(col, "postgres")
        assert mapped.target_type == "TEXT"

    def test_autoincrement_mapping_contract_per_target(self):
        mapper = SchemaMapper()
        col = ColumnSchema(name="ID", source_type="Long Integer", allow_null=False, is_autoincrement=True)
        expected = {
            "postgres": "BIGSERIAL",
            "mysql": "BIGINT AUTO_INCREMENT",
            "mariadb": "BIGINT AUTO_INCREMENT",
            "sqlite": "INTEGER",
            "sqlserver": "INT IDENTITY",
        }
        for target, expected_type in expected.items():
            mapped = mapper.map_column(col, target)
            assert mapped.target_type == expected_type

    def test_format_default_literal_contract(self):
        mapper = SchemaMapper()
        cases = {
            "": "NULL",
            "   ": "NULL",
            "NULL": "NULL",
            "true": "TRUE",
            "FALSE": "FALSE",
            "=123": "123",
            "(456)": "456",
            "='abc'": "'abc'",
            "O'Reilly": "'O''Reilly'",
            "3.14": "3.14",
        }
        for raw, expected in cases.items():
            assert mapper._format_default_literal(raw) == expected

    def test_map_table_ddl_is_deterministic(self):
        mapper = SchemaMapper()
        table = TableSchema(
            name="Orders",
            columns=[
                ColumnSchema(name="ID", source_type="Long Integer", allow_null=False, is_autoincrement=True),
                ColumnSchema(name="Status", source_type="Text", max_length=40, allow_null=False, default_value="PENDING"),
            ],
            primary_key=["ID"],
        )

        ddl1 = mapper.map_table_ddl(table, "postgres")
        ddl2 = mapper.map_table_ddl(table, "postgres")
        assert ddl1 == ddl2
        assert 'CREATE TABLE "Orders"' in ddl1
        assert 'PRIMARY KEY ("ID")' in ddl1

    def test_map_index_ddl_skips_empty_indexes(self):
        mapper = SchemaMapper()
        table = TableSchema(
            name="Orders",
            columns=[ColumnSchema(name="ID", source_type="Long Integer", allow_null=False)],
            indexes=[
                IndexSchema(name="idx_valid", columns=["ID"], is_unique=False),
                IndexSchema(name="idx_empty", columns=[], is_unique=False),
            ],
        )
        statements = mapper.map_index_ddl(table, "postgres")
        assert len(statements) == 1
        assert 'CREATE INDEX "idx_valid" ON "Orders" ("ID")' in statements[0]


class TestJetSqlGeneratorContracts:
    def test_generate_is_deterministic(self):
        parent = TableInfo(
            name="Customers",
            fields=[FieldInfo(name="ID", type="Counter", required=True)],
            primary_key=["ID"],
        )
        child = TableInfo(
            name="Orders",
            fields=[
                FieldInfo(name="ID", type="Counter", required=True),
                FieldInfo(name="CustomerID", type="Long Integer", required=True),
            ],
            primary_key=["ID"],
        )
        fk = ForeignKeyInfo(
            name="fk_orders_customers",
            columns=["CustomerID"],
            foreign_table="Customers",
            foreign_columns=["ID"],
        )

        gen = JetSqlGenerator([child, parent], relationships=[], foreign_keys=[fk])
        out1 = gen.generate()
        out2 = gen.generate()
        assert out1 == out2

    def test_generate_empty_tables_contract(self):
        gen = JetSqlGenerator([], relationships=[], foreign_keys=[])
        assert gen.generate() == []

    def test_topological_sort_places_parent_before_child(self):
        parent = TableInfo(name="P", fields=[FieldInfo(name="ID", type="Counter")], primary_key=["ID"])
        child = TableInfo(
            name="C",
            fields=[FieldInfo(name="ID", type="Counter"), FieldInfo(name="P_ID", type="Long Integer")],
            primary_key=["ID"],
        )
        fk = ForeignKeyInfo(name="fk_c_p", columns=["P_ID"], foreign_table="P", foreign_columns=["ID"])
        gen = JetSqlGenerator([child, parent], relationships=[], foreign_keys=[fk])
        stmts = gen.generate()
        p_idx = next(i for i, s in enumerate(stmts) if "CREATE TABLE [P]" in s)
        c_idx = next(i for i, s in enumerate(stmts) if "CREATE TABLE [C]" in s)
        assert p_idx < c_idx

    def test_fk_constraints_include_only_applicable_table_columns(self):
        parent = TableInfo(name="Parent", fields=[FieldInfo(name="ID", type="Counter")], primary_key=["ID"])
        child = TableInfo(
            name="Child",
            fields=[FieldInfo(name="ID", type="Counter"), FieldInfo(name="ParentID", type="Long Integer")],
            primary_key=["ID"],
        )
        unrelated = TableInfo(name="Other", fields=[FieldInfo(name="X", type="Long Integer")], primary_key=[])
        fk = ForeignKeyInfo(name="fk_child_parent", columns=["ParentID"], foreign_table="Parent", foreign_columns=["ID"])
        gen = JetSqlGenerator([child, parent, unrelated], relationships=[], foreign_keys=[fk])
        child_stmt = next(s for s in gen.generate() if "CREATE TABLE [Child]" in s)
        other_stmt = next(s for s in gen.generate() if "CREATE TABLE [Other]" in s)
        assert "FOREIGN KEY ([ParentID])" in child_stmt
        assert "FOREIGN KEY" not in other_stmt

    def test_map_type_unknown_falls_back_to_varchar_255(self):
        gen = JetSqlGenerator([], relationships=[], foreign_keys=[])
        field = FieldInfo(name="m", type="NoSuchType")
        assert gen._map_type(field) == "VARCHAR(255)"

    def test_generate_column_ddl_boolean_defaults_contract(self):
        gen = JetSqlGenerator([], relationships=[], foreign_keys=[])
        t = FieldInfo(name="Active", type="Boolean", default_value=True)
        f = FieldInfo(name="Inactive", type="Boolean", default_value=False)
        t_ddl = gen._generate_column_ddl(t)
        f_ddl = gen._generate_column_ddl(f)
        assert "DEFAULT -1" in t_ddl
        assert "DEFAULT 0" in f_ddl

    def test_generate_column_ddl_autoincrement_takes_precedence_over_default(self):
        gen = JetSqlGenerator([], relationships=[], foreign_keys=[])
        field = FieldInfo(name="ID", type="Counter", is_autoincrement=True, default_value="SHOULD_NOT_APPEAR")
        ddl = gen._generate_column_ddl(field)
        assert "AUTOINCREMENT" in ddl
        assert "DEFAULT" not in ddl
