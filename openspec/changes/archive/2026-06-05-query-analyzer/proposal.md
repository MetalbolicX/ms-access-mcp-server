# Proposal: Query Analyzer

## Intent

Provide MS Access Jet/ACE users with an `analyze_query` MCP tool to approximate query performance analysis. This addresses the lack of native `EXPLAIN ANALYZE` to help developers identify slow queries, missing indexes, and unoptimized SQL complexity.

## Scope

### In Scope
- Client-side execution timing via `SELECT COUNT(*)` or `SELECT TOP N` wrapper.
- SQL complexity scoring via regex analysis (detecting joins, subqueries, leading wildcards).
- Schema analysis to check indexes on WHERE/JOIN columns (using existing adapter methods).
- Generation of actionable performance recommendations.
- Registration of the new `analyze_query` tool.

### Out of Scope
- MS Access ShowPlan registry modification feature.
- VBA-based query profiling.
- Query plan visualization.
- Persistent query metrics history.

## Capabilities

### New Capabilities
- `query-analysis`: Provides diagnostic analysis, complexity scoring, execution timing, and index checking for MS Access SQL queries.

### Modified Capabilities
- None

## Approach

Implement a new `QueryAnalyzerService` orchestrating three steps:
1. `SQLComplexityAnalyzer`: A regex-based static parser to detect anti-patterns and score SQL complexity.
2. Execution Timer: Uses `time.perf_counter()` to run wrapped `COUNT(*)` or `TOP N` queries via existing adapter.
3. `SchemaAnalyzer`: Uses existing `get_tables()` and `get_table_schema_plan()` adapter methods to evaluate index usage.
The MCP tool `analyze_query` will expose these combined results as JSON. No changes are needed in existing adapter interfaces.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/ms_access_mcp/services/query_analyzer.py` | New | Core logic for parsing, checking schema, and orchestrating execution. |
| `src/ms_access_mcp/mcp/analysis.py` | New | The MCP tool implementation `analyze_query`. |
| `src/ms_access_mcp/mcp/server.py` | Modified | Registers the new `analyze_query` tool. |
| `tests/unit/test_query_analyzer.py` | New | Unit tests for complexity and schema analyzers. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Inaccurate parsing using regex | Medium | Use robust tests with common Access SQL patterns; keep heuristics simple. |
| Large result sets skewing timing | Low | Use `SELECT COUNT(*)` or `sample_size` wrappers to avoid data transfer overhead. |
| Missing adapter capabilities | Low | Degrade gracefully with `OdbcAdapter` (provide parsing and timing without deep index checks). |

## Rollback Plan

Remove `analyze_query` from `src/ms_access_mcp/mcp/server.py` tool registrations. Delete the new `analysis.py` tool module and `query_analyzer.py` service.

## Dependencies

- Existing `IDataAdapter` and `ISchemaAdapter` interface methods (`execute_query`, `get_tables`).
- Python standard libraries (`time`, `re`).

## Success Criteria

- [ ] `analyze_query` tool returns expected JSON payload including timing, complexity, and recommendations.
- [ ] Gracefully supports both `WinComAdapter` (full features) and `OdbcAdapter` (timing/parsing only).
- [ ] Correctly flags unoptimized patterns (e.g., leading wildcard `LIKE`).
- [ ] Unit tests pass under strict TDD.
