from typing import Literal

from pydantic import BaseModel, Field, field_validator


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
    strategy_used: Literal["batch", "linked", "passthrough", "unknown"] = "unknown"
    strategy_fallback_reason: str | None = None
    verification: "VerificationResult | None" = None


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

    @field_validator("name", "source_type")
    @classmethod
    def _normalize_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("default_value")
    @classmethod
    def _normalize_default_value(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ForeignKeySchema(BaseModel):
    name: str
    columns: list[str] = Field(default_factory=list)
    referenced_table: str
    referenced_columns: list[str] = Field(default_factory=list)


class IndexSchema(BaseModel):
    name: str
    columns: list[str] = Field(default_factory=list)
    is_unique: bool = False


class UnknownMetadata(BaseModel):
    primary_keys: bool = False
    foreign_keys: bool = False
    defaults: bool = False
    indexes: bool = False
    autoincrement: bool = False


class VerificationSignal(BaseModel):
    signal_type: Literal["count", "checksum", "sample"]
    passed: bool
    expected: str | None = None
    actual: str | None = None
    evidence: dict = Field(default_factory=dict)


class VerificationResult(BaseModel):
    table: str
    status: Literal["passed", "failed"]
    signals: list[VerificationSignal] = Field(default_factory=list)


class TableSchema(BaseModel):
    name: str
    columns: list[ColumnSchema] = Field(default_factory=list)
    primary_key: list[str] = Field(default_factory=list)
    foreign_keys: list[ForeignKeySchema] = Field(default_factory=list)
    indexes: list[IndexSchema] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _normalize_table_name(cls, value: str) -> str:
        return value.strip()


class ExtractedSchema(BaseModel):
    source: str
    version: str = "1.0"
    extracted_at: str | None = None
    tables: list[TableSchema] = Field(default_factory=list)
    relationships: list[dict] = Field(default_factory=list)
    unknown_metadata: UnknownMetadata = Field(default_factory=UnknownMetadata)


class TableTransferConfig(BaseModel):
    """Per-table overrides for column selection, WHERE filtering, and ORDER BY."""
    columns: list[str] | None = None
    where: str | None = None
    order_by: list[str] | None = None
