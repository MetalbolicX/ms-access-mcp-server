# Design: Query Analyzer

## Technical Approach

Introduce a new `analyze_query` MCP tool and a dedicated `QueryAnalyzerService` to orchestrate SQL parsing, execution timing, and schema index validation without altering existing single-responsibility `IDataAdapter` or `ISchemaAdapter` interfaces. The service will use regex-based pattern detection to evaluate SQL complexity and leverage a `SELECT COUNT(*)` wrapper for accurate execution timing across both Odbc and WinCom adapters.

## Architecture Decisions

### Decision: Service over Adapter method

**Choice**: Create a new `QueryAnalyzerService` in the service layer instead of modifying the adapter interfaces.
**Alternatives considered**: Add `analyze_query` to `IDataAdapter`.
**Rationale**: The analysis orchestrates multiple data and schema calls (`execute`, `get_tables`, `get_table_schema_plan`). The adapter layer exists for single-responsibility data access; adding this logic there would violate the Interface Segregation Principle (ISP).

### Decision: Regex-based SQL parser

**Choice**: Implement a simple regex-based parser to detect SQL complexity and patterns.
**Alternatives considered**: Use a full AST-based SQL parser like `sqlparse` or `antlr`.
**Rationale**: Avoids heavy external dependencies. The goal is pattern detection (e.g., JOIN count, subqueries, leading wildcards) to generate a complexity score and recommendations. A concise regex approach covers 95% of real-world Access queries, and edge cases are acceptable.

### Decision: COUNT(*) wrapper for timing

**Choice**: Measure execution cost by wrapping the user's query: `SELECT COUNT(*) AS _cnt FROM (user_query) AS _q`.
**Alternatives considered**: Execute the raw query and measure the total time, or use `EXPLAIN` (which MS Access lacks natively via Odbc/OLEDB in a reliable cross-adapter way).
**Rationale**: Forces the query engine to execute the full query plan without serializing large result sets over the wire. It works seamlessly across both Odbc and WinCom adapters.

### Decision: TOP N for sampling

**Choice**: Use `SELECT TOP N * FROM (user_query) AS _s` for data sampling.
**Alternatives considered**: Read N rows from a cursor and discard the rest.
**Rationale**: Directly limits data retrieval at the database engine level, providing an efficient preview of the result structure and content when `sample_size > 0`.

## Data Flow

```text
Client → analyze_query(sql, dry_run, sample_size)
                    │
                    ▼
          QueryAnalyzerService.analyze()
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
   SQLParser   SchemaAnalyzer  Executor
   (regex)     (adapter)      (adapter)
          │         │         │
          ▼         ▼         ▼
    complexity     tables    COUNT(*)
    score          indexes    timing
    details        rows       sample
          │         │         │
          └─────────┼─────────┘
                    ▼
          Recommendations
          Generator
                    │
                    ▼
              JSON result
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ms_access_mcp/services/query_analyzer.py` | Create | Service orchestration, SQL parser, and schema analysis logic. |
| `src/ms_access_mcp/mcp/analysis.py` | Create | New MCP tool definition mapping to the analyzer service. |
| `src/ms_access_mcp/mcp/server.py` | Modify | Import and register the new `analysis` tool module. |
| `tests/unit/test_query_analyzer.py` | Create | Unit tests for parser, schema analyzer, service orchestration, and recommendations. |

## Interfaces / Contracts

```python
@dataclass
class SQLParseResult:
    tables_involved: list[str]
    join_count: int
    has_subqueries: bool
    has_leading_wildcard: bool
    score: int
    complexity_details: list[str]

@dataclass
class SchemaAnalysisResult:
    tables_stats: dict[str, dict] # rows, indexes
    missing_indexes: list[str]

@dataclass
class QueryAnalysisResponse:
    success: bool
    complexity_score: int
    parse_details: SQLParseResult | None
    schema_details: SchemaAnalysisResult | None
    execution_time_ms: float | None
    total_rows: int | None
    sample_data: list[dict] | None
    recommendations: list[str]
    error: str | None
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | SQLComplexityAnalyzer | Test regex matches with 10+ known SQL patterns (JOINs, subqueries, leading wildcards). |
| Unit | SchemaAnalyzer | Mock `adapter.get_tables` and `get_table_schema_plan` to verify index detection. |
| Unit | QueryAnalyzerService | Mock adapter to verify orchestration flow: parse → timing → schema → recommendations. |
| Unit | Recommendations | Validate specific actionable text output for detected complexity patterns. |

## Migration / Rollout

No migration required. The new tool is isolated and purely additive.

## Open Questions

- None
