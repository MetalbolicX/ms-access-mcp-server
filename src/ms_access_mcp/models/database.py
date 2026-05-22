from pydantic import BaseModel, Field


class FieldInfo(BaseModel):
    name: str
    type: str
    size: int = 0
    required: bool = False
    allow_zero_length: bool = True


class TableInfo(BaseModel):
    name: str
    fields: list[FieldInfo] = Field(default_factory=list)
    record_count: int = 0


class QueryInfo(BaseModel):
    name: str
    sql: str
    type: str


class RelationshipInfo(BaseModel):
    name: str
    table: str
    foreign_table: str
    attributes: str = ""


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
