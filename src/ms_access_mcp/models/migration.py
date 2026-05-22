from pydantic import BaseModel, Field
from typing import Literal


class ErrorInfo(BaseModel):
    table: str | None = None
    row_number: int | None = None
    message: str
    timestamp: str | None = None


class TableResult(BaseModel):
    table: str
    source_rows: int = 0
    rows_transferred: int = 0
    duration_ms: int = 0
    success: bool = True
    error: str | None = None


class MigrationJob(BaseModel):
    id: str
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    phase: Literal["extract", "upload", "transfer"] = "extract"
    current_table: str | None = None
    progress: float = 0.0
    started_at: str | None = None
    completed_at: str | None = None
    results: list[TableResult] = Field(default_factory=list)
    errors: list[ErrorInfo] = Field(default_factory=list)


class ColumnSchema(BaseModel):
    name: str
    source_type: str
    max_length: int | None = None
    allow_null: bool = True
    is_autoincrement: bool = False
    default_value: str | None = None


class TableSchema(BaseModel):
    name: str
    columns: list[ColumnSchema] = Field(default_factory=list)
    primary_key: list[str] = Field(default_factory=list)


class ExtractedSchema(BaseModel):
    source: str
    version: str = "1.0"
    extracted_at: str | None = None
    tables: list[TableSchema] = Field(default_factory=list)
    relationships: list[dict] = Field(default_factory=list)