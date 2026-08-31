# Parity Findings Log

## 028-F-001: D3 Parity Truth — Stub Attribution Wrong

**Finding ID**: 028-F-001
**Phase**: Plan 028/027 COM connection lifecycle
**Discovered**: Plan 031 (2026-08-31), at commit `48388f8`
**Severity**: Historical misattribution (now corrected)

**Summary**: The 3 errored parity cases (`get_table_schema-Customers.json`,
`get_table_schema-Orders.json`, `get_table_schema-Products.json`) were attributed
during plans 027–029 to "no Access" or missing COM capability. This was wrong.

**Real root cause**: The ReScript `executeQuery` function (and adjacent schema
methods) were stubs returning `"COM executeQuery not yet fully implemented: winax binding incomplete"`
error envelopes. These were not runtime failures due to missing Access — they
were stub implementations that never attempted real COM calls.

**Evidence**: Plan 030 (`48388f8`) established that the winax binding works correctly
(`get(currentDb, "Name")` returned `"test_db.accdb"` against live Access). The
connect chain was verified working before plan 031 began.

**Plan 031 resolution**: Implements `executeQuery` via `DAO.Database.OpenRecordset`.
The 3 errored cases still error (because schema reads — `getTables`, `getTableSchemaPlan`,
etc. — are not yet implemented; that's plan 032's job), but the error messages
are now meaningful COM errors rather than "binding incomplete" stubs.

**Status**:
- `executeQuery` via DAO.OpenRecordset: RESOLVED (plan 031)
- Schema reads (the 3 remaining errored cases): plan 032+ work

**Impact on baseline**: Parity baseline 6/0/3 is unchanged in count. The error
messages for the 3 errored cases may now reflect actual COM behavior rather than
the stub message, which is the correct diagnostic state.
