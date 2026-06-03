"""Jet SQL DDL builder — generates DDL from DAO metadata.

Extracted from WinComAdapter.generate_sql() to respect SRP.
"""

from typing import Any

from ..models.database import (
    TableInfo,
    RelationshipInfo,
    ForeignKeyInfo,
    FieldInfo,
)
from ..services.sql_generator import JetSqlGenerator


class JetDdlBuilder:
    """Builds Jet SQL DDL from raw DAO metadata.

    Reads tables, relationships, and foreign keys from a ComDispatcher,
    then delegates to JetSqlGenerator for SQL generation.
    """

    def __init__(self, dispatcher: Any) -> None:
        self._dispatcher = dispatcher

    def _access_type_name(self, dao_type: int) -> str:
        """Map Access DAO type integer to human-readable type name."""
        type_map = {
            16: "Byte",
            2: "Integer",
            3: "Long Integer",
            4: "Single",
            5: "Double",
            6: "Currency",
            7: "Date/Time",
            8: "Binary",
            10: "Text",
            11: "Boolean",
            12: "Variant",
            15: "Decimal",
            17: "Unsigned Byte",
            18: "Integer",
            19: "Long Integer",
            20: "Long Integer",
            21: "Unsigned Integer",
            22: "Unsigned Long Integer",
            72: "GUID",
            128: "Binary",
            130: "Text",
            131: "Numeric",
            133: "Binary",
            134: "Char",
            135: "Numeric",
            137: "Variant",
        }
        return type_map.get(dao_type, "VARCHAR(255)")

    def read_tables(self) -> tuple[list[TableInfo], dict]:
        """Read user tables from DAO TableDefs collection.

        Returns:
            Tuple of (tables, unknown_metadata_flags dict)
        """
        unknown: dict = {
            "indexes": False,
            "primary_keys": False,
            "foreign_keys": False,
            "defaults": False,
            "autoincrement": False,
        }

        def _do() -> tuple[list[TableInfo], dict]:
            db = self._dispatcher._current_db

            base_tables: list[TableInfo] = []
            for i in range(db.TableDefs.Count):
                tdef = db.TableDefs(i)
                if tdef.Name.startswith("MSys") or tdef.Name.startswith("~"):
                    continue
                if tdef.Attributes & 0x80000000:
                    continue
                fields = []
                for j in range(tdef.Fields.Count):
                    fld = tdef.Fields(j)
                    fields.append({
                        "name": fld.Name,
                        "type": self._access_type_name(fld.Type),
                        "size": fld.Size,
                        "required": bool(fld.Required),
                        "allow_zero_length": bool(fld.AllowZeroLength),
                    })
                record_count = 0
                try:
                    rs = db.OpenRecordset(f"SELECT COUNT(*) FROM [{tdef.Name}]")
                    if not rs.EOF:
                        record_count = rs.Fields(0).Value
                    rs.Close()
                except Exception:
                    pass
                base_tables.append(TableInfo(
                    name=tdef.Name,
                    fields=fields,  # type: ignore[arg-type]
                    record_count=record_count,
                ))

            if not base_tables:
                return ([], unknown)

            tables: list[TableInfo] = []
            for base_table in base_tables:
                table_name = base_table.name

                # Get field details via direct DAO access
                field_details: list[dict] = []
                field_detail_map: dict[str, dict] = {}
                try:
                    tdef = db.TableDefs(table_name)
                    for fld in tdef.Fields:
                        default = None
                        try:
                            default = str(fld.DefaultValue) if fld.DefaultValue is not None else None
                        except Exception:
                            default = None
                        detail = {
                            "name": fld.Name,
                            "type": fld.Type,
                            "size": fld.Size,
                            "attributes": fld.Attributes,
                            "default_value": default,
                        }
                        field_details.append(detail)
                        field_detail_map[fld.Name] = detail
                except Exception:
                    pass

                # Get primary key columns via direct DAO access
                pk_columns: list[str] = []
                try:
                    tdef = db.TableDefs(table_name)
                    for idx in tdef.Indexes:
                        if idx.Primary:
                            pk_columns = [f.Name for f in idx.Fields]
                            break
                except Exception:
                    pass

                # Merge field details into FieldInfo objects
                enriched_fields: list[FieldInfo] = []
                for fld in base_table.fields:
                    detail = field_detail_map.get(fld.name, {})
                    attrs = detail.get("attributes", 0)
                    is_auto = bool(attrs & 0x10) if attrs else False
                    default_val = detail.get("default_value")

                    enriched_fields.append(FieldInfo(
                        name=fld.name,
                        type=fld.type,
                        size=fld.size,
                        required=fld.required,
                        allow_zero_length=fld.allow_zero_length,
                        is_autoincrement=is_auto,
                        default_value=default_val,
                    ))

                enriched_table = TableInfo(
                    name=table_name,
                    fields=enriched_fields,
                    record_count=base_table.record_count,
                    primary_key=pk_columns,
                )
                tables.append(enriched_table)

            return (tables, unknown)

        return self._dispatcher.call(_do)

    def read_relationships(self) -> list[RelationshipInfo]:
        """Read all foreign key relationships from DAO Relations collection."""
        def _do() -> list[RelationshipInfo]:
            relationships: list[RelationshipInfo] = []
            try:
                db = self._dispatcher._current_db
                for i in range(db.Relations.Count):
                    rel = db.Relations(i)
                    if rel.Name.startswith("~") or rel.Name.startswith("MSys"):
                        continue
                    relationships.append(RelationshipInfo(
                        name=rel.Name,
                        table=rel.Table,
                        foreign_table=rel.ForeignTable,
                        attributes=str(rel.Attributes),
                    ))
            except Exception:
                pass
            return relationships

        return self._dispatcher.call(_do)

    def read_foreign_keys(self) -> list[ForeignKeyInfo]:
        """Read foreign key column details from DAO Relations."""
        def _do() -> list[ForeignKeyInfo]:
            foreign_keys: list[ForeignKeyInfo] = []
            try:
                db = self._dispatcher._current_db
                for rel in db.Relations:
                    if rel.Name.startswith("~") or rel.Name.startswith("MSys"):
                        continue
                    child_columns: list[str] = []
                    parent_columns: list[str] = []
                    for rel_field in rel.Fields:
                        child_columns.append(rel_field.Name)
                        parent_name = getattr(rel_field, "ForeignName", rel_field.Name)
                        parent_columns.append(parent_name)
                    foreign_keys.append(ForeignKeyInfo(
                        name=rel.Name,
                        columns=child_columns,
                        foreign_table=rel.ForeignTable,
                        foreign_columns=parent_columns,
                    ))
            except Exception:
                pass
            return foreign_keys

        return self._dispatcher.call(_do)

    def generate(self) -> tuple[list[TableInfo], list[RelationshipInfo], list[ForeignKeyInfo], dict]:
        """Generate full schema: tables, relationships, foreign keys, and unknown metadata flags.

        Returns:
            Tuple of (tables, relationships, foreign_keys, unknown_metadata_flags)
        """
        tables, unknown = self.read_tables()
        relationships = self.read_relationships()
        foreign_keys = self.read_foreign_keys()
        return (tables, relationships, foreign_keys, unknown)

    def write(self, output_path: str) -> dict:
        """Generate DDL and write to output_path.

        Args:
            output_path: Path to write the DDL SQL file.

        Returns:
            dict with success=True, path, statements (count), tables (list)
        """
        tables, relationships, foreign_keys, unknown = self.generate()

        if not tables:
            return {"success": True, "path": output_path, "statements": 0, "tables": []}

        generator = JetSqlGenerator(tables, relationships, foreign_keys)
        statements = generator.generate()

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(statements))
            if statements:
                f.write("\n")

        return {
            "success": True,
            "path": output_path,
            "statements": len(statements),
            "tables": [t.name for t in tables],
        }