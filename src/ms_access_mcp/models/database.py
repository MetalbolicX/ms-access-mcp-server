from pydantic import BaseModel, Field


class FieldInfo(BaseModel):
    name: str
    type: str
    size: int = 0
    required: bool = False
    allow_zero_length: bool = True
    default_value: str | int | float | bool | None = None
    is_autoincrement: bool = False


class TableInfo(BaseModel):
    name: str
    fields: list[FieldInfo] = Field(default_factory=list)
    record_count: int = 0
    primary_key: list[str] = Field(default_factory=list)


class QueryInfo(BaseModel):
    name: str
    sql: str
    type: str


class RelationshipInfo(BaseModel):
    name: str
    table: str
    foreign_table: str
    attributes: str = ""


class ForeignKeyInfo(BaseModel):
    name: str
    columns: list[str]  # child columns
    foreign_table: str  # parent table
    foreign_columns: list[str]  # parent columns


class ControlInfo(BaseModel):
    name: str
    type: str
    properties: dict = Field(default_factory=dict)


class FormInfo(BaseModel):
    name: str
    record_source: str = ""
    controls: list[ControlInfo] = Field(default_factory=list)


class ReportInfo(BaseModel):
    name: str
    record_source: str = ""
    controls: list[ControlInfo] = Field(default_factory=list)


class MacroInfo(BaseModel):
    name: str
    type: str = "Macro"


class ModuleInfo(BaseModel):
    name: str
    type: str = "Module"
    code: str = ""


class QueryResult(BaseModel):
    """Result of a query execution."""
    success: bool
    rows: list[dict]
    count: int
    columns: list[str]
    error: str | None = None


class LinkedTableInfo(BaseModel):
    name: str
    source_table: str
    connect_string: str
    type: str = "ODBC"
    attributes: int = 0  # DAO dbHiddenObject flag (0x00000001)


class IndexInfo(BaseModel):
    """Describes an index on a table — used by get_indexes."""

    name: str
    columns: list[str] = Field(default_factory=list)
    is_unique: bool = False
    is_primary: bool = False
    ignore_nulls: bool = False
