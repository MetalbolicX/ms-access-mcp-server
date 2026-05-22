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
