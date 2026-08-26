# Fixture inventory - tests/integration/fixtures/test_db.accdb

Generated: 2026-08-25T20:38:51.081768
File size: 462848 bytes
File mtime: 2026-08-25T20:37:01.814414
Source: tests/integration/fixtures/test_db.accdb (Python oracle)
Driver: `Microsoft Access Driver (*.mdb, *.accdb)` via pyodbc

## User tables (3)

### `Customers` (3 rows)

| Column | Type | Nullable |
|--------|------|----------|
| `ID` | `integer` | yes |
| `Name` | `string` | yes |

### `Orders` (3 rows)

| Column | Type | Nullable |
|--------|------|----------|
| `ID` | `integer` | yes |
| `CustomerID` | `integer` | yes |
| `Total` | `double` | yes |

### `Products` (2 rows)

| Column | Type | Nullable |
|--------|------|----------|
| `ID` | `integer` | yes |
| `Name` | `string` | yes |
| `Price` | `double` | yes |

## Foreign-key relationships (heuristic)

- `Orders.CustomerID` -> `Customers.ID` (heuristic: column name ends in `ID`, matches primary key of another table)

## Saved queries (0)

- (none detected - `MSysAccessStorage WHERE Type = 5` was empty for this fixture)

## Notes

- MSysObjects ACL-blocked by Access (error -1907, "no read permission on MSysObjects") in this fixture; discovery uses probe-based candidate enumeration instead.
- MSysAccessStorage is internal Access workspace scaffolding, not user tables - verified during plan 016.
- Discovery strategy: probe-based candidate enumeration against the candidate list (env var `ACCESS_FIXTURE_TABLE_CANDIDATES`).
- Row counts taken via `SELECT COUNT(*) FROM [<name>]`; columns via `SELECT * FROM [<name>] WHERE 1=0` + `cur.description`.
- Probed 28 candidate names; override via `ACCESS_FIXTURE_TABLE_CANDIDATES` (semicolon-separated).
