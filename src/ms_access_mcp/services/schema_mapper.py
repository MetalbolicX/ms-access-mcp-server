from pydantic import BaseModel
from ..models.migration import ColumnSchema, TableSchema

# Type mapping tables
TYPE_MAP = {
    "postgres": {
        "Text": "VARCHAR({max_length})",
        "Memo": "TEXT",
        "Long Integer": "BIGINT",
        "Integer": "INTEGER",
        "Byte": "SMALLINT",
        "Boolean": "BOOLEAN",
        "Date/Time": "TIMESTAMP(0)",
        "Currency": "DECIMAL(19,4)",
        "Counter": "BIGSERIAL",
        "AutoNumber": "BIGSERIAL",
        "Single": "REAL",
        "Double": "DOUBLE PRECISION",
        "Decimal": "DECIMAL(18,4)",
        "OLE Object": "BYTEA",
        "GUID": "Uuid",
        "Binary": "BYTEA",
    },
    "mysql": {
        "Text": "VARCHAR({max_length})",
        "Memo": "LONGTEXT",
        "Long Integer": "BIGINT",
        "Integer": "INT",
        "Byte": "TINYINT UNSIGNED",
        "Boolean": "TINYINT(1)",
        "Date/Time": "DATETIME",
        "Currency": "DECIMAL(19,4)",
        "Counter": "BIGINT AUTO_INCREMENT",
        "AutoNumber": "BIGINT AUTO_INCREMENT",
        "Single": "FLOAT",
        "Double": "DOUBLE",
        "Decimal": "DECIMAL(18,4)",
        "OLE Object": "LONGBLOB",
        "GUID": "CHAR(36)",
        "Binary": "LONGBLOB",
    },
    "mariadb": {
        "Text": "VARCHAR({max_length})",
        "Memo": "LONGTEXT",
        "Long Integer": "BIGINT",
        "Integer": "INT",
        "Byte": "TINYINT UNSIGNED",
        "Boolean": "TINYINT(1)",
        "Date/Time": "DATETIME",
        "Currency": "DECIMAL(19,4)",
        "Counter": "BIGINT AUTO_INCREMENT",
        "AutoNumber": "BIGINT AUTO_INCREMENT",
        "Single": "FLOAT",
        "Double": "DOUBLE",
        "Decimal": "DECIMAL(18,4)",
        "OLE Object": "LONGBLOB",
        "GUID": "CHAR(36)",
        "Binary": "LONGBLOB",
    },
    "sqlite": {
        "Text": "TEXT",
        "Memo": "TEXT",
        "Long Integer": "INTEGER",
        "Integer": "INTEGER",
        "Byte": "INTEGER",
        "Boolean": "INTEGER",
        "Date/Time": "TEXT",
        "Currency": "REAL",
        "Counter": "INTEGER",
        "AutoNumber": "INTEGER",
        "Single": "REAL",
        "Double": "REAL",
        "Decimal": "REAL",
        "OLE Object": "BLOB",
        "GUID": "TEXT",
        "Binary": "BLOB",
    },
    "sqlserver": {
        "Text": "VARCHAR({max_length})",
        "Memo": "VARCHAR(max)",
        "Long Integer": "INT",
        "Integer": "SMALLINT",
        "Byte": "TINYINT",
        "Boolean": "BIT",
        "Date/Time": "DATETIME2(0)",
        "Currency": "MONEY",
        "Counter": "INT IDENTITY",
        "AutoNumber": "INT IDENTITY",
        "Single": "REAL",
        "Double": "FLOAT",
        "Decimal": "DECIMAL(18,4)",
        "OLE Object": "VARBINARY(max)",
        "GUID": "UNIQUEIDENTIFIER",
        "Binary": "VARBINARY(max)",
    },
}


class MappedColumn(BaseModel):
    name: str
    target_type: str
    allow_null: bool
    is_primary_key: bool = False
    is_autoincrement: bool = False


class SchemaMapper:
    """Maps Access column types to target database types."""

    @staticmethod
    def _format_default_literal(value: str) -> str:
        raw = value.strip()
        if not raw:
            return "NULL"

        # Common Access default wrappers: =VALUE / (VALUE)
        if raw.startswith("="):
            raw = raw[1:].strip()
        if raw.startswith("(") and raw.endswith(")"):
            raw = raw[1:-1].strip()

        lowered = raw.lower()
        if lowered in {"null", "true", "false"}:
            return lowered.upper()

        if raw.startswith("'") and raw.endswith("'"):
            return raw

        if raw.replace(".", "", 1).isdigit():
            return raw

        escaped = raw.replace("'", "''")
        return f"'{escaped}'"

    def map_column(self, column: ColumnSchema, target_type: str) -> MappedColumn:
        """Map a single Access column to target database type."""
        type_map = TYPE_MAP.get(target_type, TYPE_MAP["postgres"])
        source_type = column.source_type

        # Handle autoincrement
        if column.is_autoincrement:
            if target_type == "postgres":
                mapped_type = "BIGSERIAL"
            elif target_type in ("mysql", "mariadb"):
                mapped_type = "BIGINT AUTO_INCREMENT"
            elif target_type == "sqlite":
                mapped_type = "INTEGER"
            elif target_type == "sqlserver":
                mapped_type = "INT IDENTITY"
            else:
                mapped_type = type_map.get(source_type, "INTEGER")
        else:
            template = type_map.get(source_type, "TEXT")
            if "{max_length}" in template:
                max_len = column.max_length or 255
                mapped_type = template.format(max_length=max_len)
            else:
                mapped_type = template

        return MappedColumn(
            name=column.name,
            target_type=mapped_type,
            allow_null=column.allow_null,
            is_primary_key=False,
            is_autoincrement=column.is_autoincrement,
        )

    def map_table_ddl(self, table: TableSchema, target_type: str) -> str:
        """Generate DDL for creating a table in target database."""
        lines = []
        pk_cols = []
        fk_defs = []

        for col in table.columns:
            mapped = self.map_column(col, target_type)
            col_def = f'"{mapped.name}" {mapped.target_type}'
            if not mapped.allow_null:
                col_def += " NOT NULL"
            if col.default_value is not None:
                col_def += f" DEFAULT {self._format_default_literal(col.default_value)}"
            if mapped.is_autoincrement and target_type not in ("sqlserver",):
                pass  # autoincrement is part of type
            lines.append(col_def)
            if col.name in table.primary_key:
                pk_cols.append(f'"{mapped.name}"')

        for fk in table.foreign_keys:
            if not fk.columns or not fk.referenced_columns:
                continue
            child_cols = ", ".join(f'"{column}"' for column in fk.columns)
            parent_cols = ", ".join(f'"{column}"' for column in fk.referenced_columns)
            fk_defs.append(
                f'CONSTRAINT "{fk.name}" FOREIGN KEY ({child_cols}) '
                f'REFERENCES "{fk.referenced_table}" ({parent_cols})'
            )

        sql = f'CREATE TABLE "{table.name}" (\n  '
        sql += ",\n  ".join(lines)
        if pk_cols:
            sql += f",\n  PRIMARY KEY ({', '.join(pk_cols)})"
        if fk_defs:
            sql += ",\n  " + ",\n  ".join(fk_defs)
        sql += "\n)"
        return sql

    def map_index_ddl(self, table: TableSchema, target_type: str) -> list[str]:
        """Generate index DDL statements for a table.

        The output stays target-agnostic at orchestration level; connector-specific
        execution remains encapsulated in connectors.
        """
        _ = target_type  # reserved for future dialect-specific quoting.

        statements: list[str] = []
        for index in table.indexes:
            if not index.columns:
                continue
            qualifier = "UNIQUE " if index.is_unique else ""
            columns = ", ".join(f'"{column}"' for column in index.columns)
            statements.append(
                f'CREATE {qualifier}INDEX "{index.name}" ON "{table.name}" ({columns})'
            )
        return statements
