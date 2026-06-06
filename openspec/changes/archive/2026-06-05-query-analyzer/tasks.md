# Tasks: Query Analyzer

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 280-350 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Deliver parser, service, MCP tool, and tests | Single PR | Keep RED→GREEN→REFACTOR flow inside the same branch |

## Phase 1: Foundation ✅

- [x] 1.1 Create `tests/unit/test_query_analyzer.py` RED cases for simple/heavy scoring, subquery/correlated detection, leading wildcard, WHERE function, cartesian join, and non-SELECT rejection.
- [x] 1.2 Create `src/ms_access_mcp/services/query_analyzer.py` with `SQLParseResult` helpers, scoring constants, regex patterns, and table/column extraction helpers for WHERE/JOIN analysis.
- [x] 1.3 Add RED schema tests with mock WinComAdapter and OdbcAdapter.

## Phase 2: Core Implementation

- [x] 2.1 Implement `SQLComplexityAnalyzer.parse()` in `src/ms_access_mcp/services/query_analyzer.py` to detect JOIN/subquery/DISTINCT/ORDER BY/GROUP BY/aggregate/NOT IN/OR/UNION patterns and map score to simple/moderate/complex/heavy.
- [x] 2.2 Implement `SchemaAnalyzer.analyze()` in `src/ms_access_mcp/services/query_analyzer.py` to filter parsed tables, collect row/field counts, flatten indexed columns from `TableSchema.indexes`, and flag unindexed WHERE/JOIN columns.
- [x] 2.3 Implement `QueryAnalyzerService.analyze()` in `src/ms_access_mcp/services/query_analyzer.py` to validate non-empty SELECT SQL, run parse → schema, wrap timing with `SELECT COUNT(*) AS _cnt FROM (...)`, and run `SELECT TOP N * FROM (...)` sampling when allowed.
- [x] 2.4 Add recommendation generation in `src/ms_access_mcp/services/query_analyzer.py` for missing indexes, leading wildcard LIKE, cartesian joins, correlated subqueries, `NOT IN`, `OR`, and clean-query/no-issues output.

## Phase 3: Testing ✅

- [x] 3.1 Expand coverage: dry_run, timed execution, sample mode, partial timing failure, recommendation text.
- [x] 3.2 Adapter comparison: WinCom full index data, OdbcAdapter graceful fallback.
- [x] 3.3 Refactored mocks/fixtures, fixed SchemaAnalyzer `index_info_available` logic bug.

## Phase 4: Wiring ✅

- [x] 4.1 Create `src/ms_access_mcp/mcp/analysis.py` with `analyze_query()` tool.
- [x] 4.2 Wire in `server.py` — import + re-export.
- [x] 4.3 MCP binding tests in `tests/unit/test_analysis_mcp.py` (blocked by env, not code).
