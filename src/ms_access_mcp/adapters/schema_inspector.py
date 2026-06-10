"""SchemaInspector — DAO schema introspection operations for COM automation.

Extracted from WinComAdapter to respect SRP. All methods use self._dispatcher.call(_do)
except generate_sql which needs direct self._dispatcher.current_db access to avoid
nested dispatch deadlock.
"""

import logging
import os
from datetime import datetime

from ..adapters.com_dispatcher import ComDispatcher

logger = logging.getLogger(__name__)
from ..models.database import (
    FieldInfo,
    ForeignKeyInfo,
    IndexInfo,
    QueryInfo,
    RelationshipInfo,
    TableInfo,
)
from ..models.migration import (
    ColumnSchema,
    ForeignKeySchema,
    IndexSchema,
    TableSchema,
    UnknownMetadata,
)


class SchemaInspector:
    """DAO schema introspection — tables, indexes, relationships, metadata, SQL generation.

    Args:
        dispatcher: ComDispatcher instance for STA-threaded COM calls.
    """

    def __init__(self, dispatcher: ComDispatcher) -> None:
        self._dispatcher = dispatcher

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _access_type_name(access_type: int) -> str:
        """Map Access data type integer to string name."""
        type_map = {
            1: "Boolean",
            2: "Byte",
            3: "Integer",
            4: "Long Integer",
            5: "Currency",
            6: "Single",
            7: "Double",
            8: "Date/Time",
            10: "Text",
            11: "Binary",
            12: "Memo",
            15: "GUID",
            16: "Big Integer",
            17: "Unsigned Byte",
            18: "Unsigned Integer",
            19: "Unsigned Long Integer",
            20: "Decimal",
        }
        return type_map.get(access_type, f"Unknown({access_type})")

    # ------------------------------------------------------------------ #
    # get_tables
    # ------------------------------------------------------------------ #

    def get_tables(self) -> list[TableInfo]:
        """Get all user tables from the connected database."""
        if not self._dispatcher.is_connected():
            return []

        def _do() -> list[TableInfo]:
            tables: list[TableInfo] = []
            try:
                db = self._dispatcher.current_db
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

                    tables.append(TableInfo(
                        name=tdef.Name,
                        fields=fields,
                        record_count=record_count,
                    ))
            except Exception as e:
                logger.warning("get_tables failed: %s", e, exc_info=True)
            return tables

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # get_system_tables
    # ------------------------------------------------------------------ #

    def get_system_tables(self) -> list[TableInfo]:
        """Get system tables from the database."""
        if not self._dispatcher.is_connected():
            return []

        def _do() -> list[TableInfo]:
            tables: list[TableInfo] = []
            try:
                db = self._dispatcher.current_db
                for i in range(db.TableDefs.Count):
                    tdef = db.TableDefs(i)
                    if tdef.Name.startswith("MSys"):
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
                        tables.append(TableInfo(name=tdef.Name, fields=fields, record_count=0))
            except Exception:
                pass
            return tables

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # get_queries
    # ------------------------------------------------------------------ #

    def get_queries(self) -> list[QueryInfo]:
        """Get all saved queries (QueryDefs) from the connected database.

        Excludes system queries (names starting with '~' or 'MSys').
        Returns list of QueryInfo with name, sql, and type.
        """
        if not self._dispatcher.is_connected():
            return []

        def _do() -> list[QueryInfo]:
            queries: list[QueryInfo] = []
            try:
                db = self._dispatcher.current_db
                for i in range(db.QueryDefs.Count):
                    qdef = db.QueryDefs(i)
                    name = qdef.Name
                    if name.startswith("~") or name.startswith("MSys"):
                        continue
                    sql = ""
                    try:
                        sql = qdef.SQL
                    except Exception:
                        pass
                    qtype = "select"
                    try:
                        if qdef.Type == 32:  # dbQProcedure
                            qtype = "action"
                        elif qdef.Type == 80:  # dbQDDL
                            qtype = "ddl"
                    except Exception:
                        pass
                    queries.append(QueryInfo(name=name, sql=sql, type=qtype))
            except Exception as e:
                logger.warning("get_queries failed: %s", e, exc_info=True)
            return queries

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # _get_table_indexes
    # ------------------------------------------------------------------ #

    def _get_table_indexes(self, table_name: str) -> dict[str, list[str]]:
        """Return {index_name: [columns]} for indexes where Primary=True.

        .. deprecated::
            Use get_indexes() instead, which returns all indexes as IndexInfo objects.
            This method is kept for backward compatibility with internal callers.
        """
        if not self._dispatcher.is_connected():
            return {}

        def _do() -> dict[str, list[str]]:
            indexes: dict[str, list[str]] = {}
            try:
                db = self._dispatcher.current_db
                tdef = db.TableDefs(table_name)
                for idx in tdef.Indexes:
                    if idx.Primary:
                        indexes[idx.Name] = [f.Name for f in idx.Fields]
            except Exception:
                pass
            return indexes

        return self._dispatcher.call(_do)

    def get_indexes(self, table_name: str) -> list[IndexInfo]:
        """Return all indexes (primary + secondary) for a table as IndexInfo objects.

        Unlike _get_table_indexes which only returned primary indexes,
        this method returns ALL indexes on the table.
        """
        if not self._dispatcher.is_connected():
            return []

        def _do() -> list[IndexInfo]:
            result: list[IndexInfo] = []
            try:
                db = self._dispatcher.current_db
                tdef = db.TableDefs(table_name)
                for idx in tdef.Indexes:
                    columns = [f.Name for f in idx.Fields]
                    if not columns:
                        continue
                    result.append(IndexInfo(
                        name=idx.Name,
                        columns=columns,
                        is_unique=bool(getattr(idx, "Unique", False)),
                        is_primary=bool(getattr(idx, "Primary", False)),
                        ignore_nulls=bool(getattr(idx, "IgnoreNulls", False)),
                    ))
            except Exception:
                pass
            return result

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # _get_field_details
    # ------------------------------------------------------------------ #

    def _get_field_details(self, table_name: str) -> list[dict]:
        """Return list of {name, type, size, attributes, default_value} for each field."""
        if not self._dispatcher.is_connected():
            return []

        def _do() -> list[dict]:
            fields: list[dict] = []
            try:
                db = self._dispatcher.current_db
                tdef = db.TableDefs(table_name)
                for fld in tdef.Fields:
                    default = None
                    try:
                        default = str(fld.DefaultValue) if fld.DefaultValue is not None else None
                    except Exception:
                        default = None
                    fields.append({
                        "name": fld.Name,
                        "type": fld.Type,
                        "size": fld.Size,
                        "attributes": fld.Attributes,
                        "default_value": default,
                    })
            except Exception:
                pass
            return fields

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # _get_relationship_columns
    # ------------------------------------------------------------------ #

    def _get_relationship_columns(self) -> list[ForeignKeyInfo]:
        """Read Relations collection and build ForeignKeyInfo list."""
        if not self._dispatcher.is_connected():
            return []

        def _do() -> list[ForeignKeyInfo]:
            fks: list[ForeignKeyInfo] = []
            try:
                db = self._dispatcher.current_db
                for rel in db.Relations:
                    if rel.Name.startswith("~") or rel.Name.startswith("MSys"):
                        continue
                    cols = [f.Name for f in rel.Fields]
                    fks.append(ForeignKeyInfo(
                        name=rel.Name,
                        columns=cols,
                        foreign_table=rel.ForeignTable,
                        foreign_columns=cols,
                    ))
            except Exception:
                pass
            return fks

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # get_table_schema_plan
    # ------------------------------------------------------------------ #

    def get_table_schema_plan(self) -> tuple[list[TableSchema], UnknownMetadata]:
        """Extract table schema fidelity metadata from Access DAO collections.

        Saved queries are intentionally excluded by using only table definitions.
        """
        if not self._dispatcher.is_connected():
            return ([], UnknownMetadata())

        def _do() -> tuple[list[TableSchema], UnknownMetadata]:
            schema_tables: list[TableSchema] = []
            unknown = UnknownMetadata()

            try:
                db = self._dispatcher.current_db

                relationships_by_table: dict[str, list[ForeignKeySchema]] = {}
                try:
                    for rel in db.Relations:
                        if rel.Name.startswith("~") or rel.Name.startswith("MSys"):
                            continue

                        child_columns: list[str] = []
                        parent_columns: list[str] = []
                        for rel_field in rel.Fields:
                            child_columns.append(rel_field.Name)
                            parent_name = getattr(rel_field, "ForeignName", rel_field.Name)
                            parent_columns.append(parent_name)

                        fk = ForeignKeySchema(
                            name=rel.Name,
                            columns=parent_columns,
                            referenced_table=rel.Table,
                            referenced_columns=child_columns,
                        )
                        relationships_by_table.setdefault(rel.ForeignTable, []).append(fk)
                except Exception:
                    unknown.foreign_keys = True

                for tdef in db.TableDefs:
                    table_name = tdef.Name
                    if table_name.startswith("MSys") or table_name.startswith("~"):
                        continue
                    if tdef.Attributes & 0x80000000:
                        continue

                    columns: list[ColumnSchema] = []
                    primary_key: list[str] = []
                    indexes: list[IndexSchema] = []

                    for fld in tdef.Fields:
                        default_value = None
                        try:
                            raw_default = fld.DefaultValue
                            default_value = str(raw_default) if raw_default is not None else None
                        except Exception:
                            unknown.defaults = True

                        attributes = int(getattr(fld, "Attributes", 0) or 0)
                        is_autoincrement = bool(attributes & 0x10)

                        columns.append(
                            ColumnSchema(
                                name=fld.Name,
                                source_type=self._access_type_name(fld.Type),
                                max_length=fld.Size if fld.Size and fld.Size > 0 else None,
                                allow_null=not bool(getattr(fld, "Required", False)),
                                is_autoincrement=is_autoincrement,
                                default_value=default_value,
                            )
                        )

                    try:
                        for idx in tdef.Indexes:
                            idx_fields = [idx_field.Name for idx_field in idx.Fields]
                            if not idx_fields:
                                continue
                            if bool(getattr(idx, "Primary", False)):
                                primary_key = idx_fields
                                continue
                            indexes.append(
                                IndexSchema(
                                    name=idx.Name,
                                    columns=idx_fields,
                                    is_unique=bool(getattr(idx, "Unique", False)),
                                )
                            )
                    except Exception:
                        unknown.indexes = True
                        unknown.primary_keys = True

                    if not primary_key:
                        unknown.primary_keys = True

                    if any(col.is_autoincrement for col in columns) and not primary_key:
                        unknown.autoincrement = True

                    schema_tables.append(
                        TableSchema(
                            name=table_name,
                            columns=columns,
                            primary_key=primary_key,
                            foreign_keys=relationships_by_table.get(table_name, []),
                            indexes=indexes,
                        )
                    )
            except Exception:
                unknown.primary_keys = True
                unknown.foreign_keys = True
                unknown.defaults = True
                unknown.indexes = True
                unknown.autoincrement = True
                return ([], unknown)

            return (schema_tables, unknown)

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # get_relationships
    # ------------------------------------------------------------------ #

    def get_relationships(self) -> list[RelationshipInfo]:
        """Get all foreign key relationships from DAO Relations collection."""
        if not self._dispatcher.is_connected():
            return []

        def _do() -> list[RelationshipInfo]:
            relationships: list[RelationshipInfo] = []
            try:
                db = self._dispatcher.current_db
                for i in range(db.Relations.Count):
                    rel = db.Relations(i)
                    if rel.Name.startswith("~") or rel.Name.startswith("MSys"):
                        continue
                    child_cols = []
                    parent_cols = []
                    for j in range(rel.Fields.Count):
                        child_cols.append(rel.Fields(j).Name)
                        parent_cols.append(rel.Fields(j).ForeignName)
                    relationships.append(RelationshipInfo(
                        name=rel.Name,
                        table=rel.Table,
                        foreign_table=rel.ForeignTable,
                        attributes=str(rel.Attributes),
                        columns=child_cols,
                        foreign_columns=parent_cols,
                    ))
            except Exception as e:
                logger.warning("get_relationships failed: %s", e, exc_info=True)
            return relationships

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # create_relationship
    # ------------------------------------------------------------------ #

    def create_relationship(
        self,
        table_name: str,
        relationship_name: str,
        columns: list[str],
        foreign_table: str,
        foreign_columns: list[str],
    ) -> dict:
        """Create a foreign key relationship via DAO.

        Args:
            table_name: Child table containing the foreign key
            relationship_name: Name for the new relation
            columns: List of column names in the child table
            foreign_table: Parent table being referenced
            foreign_columns: List of column names in the parent table

        Returns:
            dict with success=True or success=False and error
        """
        if not self._dispatcher.is_connected():
            return {"success": False, "error": "Not connected"}
        if len(columns) != len(foreign_columns):
            return {
                "success": False,
                "error": "columns and foreign_columns must have same length",
            }

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                rel = db.CreateRelation(relationship_name, table_name, foreign_table)
                for i in range(len(columns)):
                    f = rel.CreateField(columns[i])
                    f.ForeignName = foreign_columns[i]
                    rel.Fields.Append(f)
                db.Relations.Append(rel)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # delete_relationship
    # ------------------------------------------------------------------ #

    def delete_relationship(self, table_name: str, relationship_name: str) -> dict:
        """Delete a foreign key relationship via DAO.

        Args:
            table_name: Child table containing the constraint
            relationship_name: Name of the relation to drop

        Returns:
            dict with success=True or success=False and error
        """
        if not self._dispatcher.is_connected():
            return {"success": False, "error": "Not connected"}

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db
                db.Relations.Delete(relationship_name)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # get_object_metadata
    # ------------------------------------------------------------------ #

    def get_object_metadata(self, object_name: str) -> dict:
        """Get metadata for a database object."""
        if not self._dispatcher.is_connected():
            return {}

        # Check tables first
        try:
            for table in self.get_tables():
                if table.name == object_name:
                    return {
                        "name": table.name,
                        "type": "table",
                        "properties": {"record_count": str(table.record_count)},
                    }
        except Exception:
            pass

        # Check forms, reports, macros via COM dispatch
        def _do() -> dict:
            for collection_name in ["AllForms", "AllReports", "AllMacros"]:
                try:
                    collection = getattr(self._dispatcher.access_app.CurrentProject, collection_name)
                    for i in range(collection.Count):
                        obj = collection(i)
                        if obj.Name == object_name:
                            props = {}
                            try:
                                for prop in obj.Properties:
                                    props[prop.Name] = str(prop.Value)
                            except Exception:
                                pass
                            return {
                                "name": obj.Name,
                                "type": collection_name.replace("All", "").lower(),
                                "properties": props,
                            }
                except Exception:
                    pass
            return {}

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # generate_sql
    # ------------------------------------------------------------------ #

    def get_database_statistics(self) -> dict:
        """Get O(1) database statistics — counts, file info, version.

        Returns dict with top-level keys: success, objects, file, system.
        Returns zero counts with com_available=False when not connected.
        """
        if not self._dispatcher.is_connected():
            return {
                "success": True,
                "objects": {
                    "tables": 0, "queries": 0, "forms": 0,
                    "reports": 0, "macros": 0, "modules": 0,
                },
                "file": {"name": "", "size_bytes": 0, "modified": ""},
                "system": {"access_version": None, "com_available": False},
            }

        def _do() -> dict:
            try:
                app = self._dispatcher.access_app
                db = app.CurrentDb
                project = app.CurrentProject

                objects = {
                    "tables": int(db.TableDefs.Count),
                    "queries": int(db.QueryDefs.Count),
                    "forms": int(project.AllForms.Count),
                    "reports": int(project.AllReports.Count),
                    "macros": int(project.AllMacros.Count),
                    "modules": int(project.AllModules.Count),
                }

                # File info — db.Name is the full path to the .accdb file
                db_path = str(db.Name)
                stat = os.stat(db_path)
                file_info = {
                    "name": os.path.basename(db_path),
                    "size_bytes": int(stat.st_size),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }

                system_info = {
                    "access_version": str(app.Version),
                    "com_available": True,
                }

                return {
                    "success": True,
                    "objects": objects,
                    "file": file_info,
                    "system": system_info,
                }
            except Exception as e:
                logger.warning("get_database_statistics failed: %s", e, exc_info=True)
                return {
                    "success": True,
                    "objects": {
                        "tables": 0, "queries": 0, "forms": 0,
                        "reports": 0, "macros": 0, "modules": 0,
                    },
                    "file": {"name": "", "size_bytes": 0, "modified": ""},
                    "system": {"access_version": None, "com_available": False},
                }

        return self._dispatcher.call(_do)

    def generate_sql(self, output_path: str) -> dict:
        """Generate Jet SQL DDL and write to output_path.

        Orchestrates reading schema (tables, indexes, field details, FKs),
        calls JetSqlGenerator.generate(), and writes to output_path.

        Uses self._dispatcher.current_db DIRECTLY (not via call()) to avoid
        nested dispatch deadlock. This is the same pattern used in the original
        WinComAdapter.generate_sql.

        Returns:
            dict with success=True, path, statements (count), tables (list)
        """
        if not self._dispatcher.is_connected():
            return {"success": False, "error": "Not connected"}

        from ..services.sql_generator import JetSqlGenerator

        def _do() -> dict:
            try:
                db = self._dispatcher.current_db

                # 1. Read tables directly from DAO (avoid nested dispatch deadlock)
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
                        fields=fields,
                        record_count=record_count,
                    ))

                if not base_tables:
                    return {"success": True, "path": output_path, "statements": 0, "tables": []}

                # 2. Enrich each table with field details and primary keys
                tables: list[TableInfo] = []
                for base_table in base_tables:
                    table_name = base_table.name

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

                    pk_columns: list[str] = []
                    try:
                        tdef = db.TableDefs(table_name)
                        for idx in tdef.Indexes:
                            if idx.Primary:
                                pk_columns = [f.Name for f in idx.Fields]
                                break
                    except Exception:
                        pass

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

                # 3. Get relationships via direct DAO access
                relationships: list[RelationshipInfo] = []
                try:
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

                foreign_keys: list[ForeignKeyInfo] = []
                try:
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

                # 4. Generate SQL
                generator = JetSqlGenerator(tables, relationships, foreign_keys)
                statements = generator.generate()

                # 5. Write to output_path
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
            except Exception as e:
                return {"success": False, "error": str(e)}

        return self._dispatcher.call(_do)
