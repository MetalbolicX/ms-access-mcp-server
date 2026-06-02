# Design: migration-sqlite-tests

## Technical Approach

We will test `MigrationService` directly against a real `.accdb` file via the `WinComAdapter`, mirroring the pattern in `test_real_adapter.py`. The `.accdb` fixture will be expanded to include realistic seed data and a comprehensive type-testing table (`type_test`). For SQLite verification, we will use raw `sqlite3` connections to check the output target database schema and row values directly without depending on `SqliteConnector` logic, ensuring we test the overall system correctness independently of the connector implementation.

## Architecture Decisions

### Decision: Direct MigrationService Testing

**Choice**: Instantiate and test `MigrationService` directly with `WinComAdapter` in the integration test.
**Alternatives considered**: Calling the high-level MCP tool handlers with global dependencies.
**Rationale**: Avoids the complexity of mocking globals or setting up MCP context. Provides direct access to `adapter.connect()`, `MigrationService.extract_schema()`, and `transfer_data()`.

### Decision: SQLite Verification Strategy

**Choice**: Use Python's built-in `sqlite3.connect()` to verify the generated SQLite database file.
**Alternatives considered**: Using `SqliteConnector.get_row_count()` and similar internal methods.
**Rationale**: By verifying with `sqlite3`, we validate the actual raw output state independently of the internal tool components. It proves the connector correctly emitted standard SQLite artifacts.

### Decision: Fixture Update Strategy

**Choice**: Append seed data and new `type_test` table logic to `generate_fixture.py`.
**Alternatives considered**: Committing a pre-built `.accdb` file with these values, or creating a new separate fixture generation script.
**Rationale**: `generate_fixture.py` already creates the DB reliably across test runs via Win32COM. Modifying it ensures all integration tests share a consistent and well-understood dataset without checking binary files into git.

## Data Flow

    Test Setup ──→ generate_fixture.py (creates .accdb)
         │
         ▼
    WinComAdapter (connects to .accdb)
         │
         ▼
    MigrationService.extract_schema() ──→ ExtractedSchema (Memory)
         │
         ▼
    MigrationService.upload_schema() ──→ SQLite .db file (tempdir)
         │
         ▼
    MigrationService.transfer_data() ──→ SQLite .db file (tempdir)
         │
         ▼
    sqlite3.connect() ──→ Verification (Assert counts, types, data)

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `tests/integration/generate_fixture.py` | Modify | Add `type_test` table creation and `INSERT INTO` queries for sample data (3+ rows) |
| `tests/integration/test_migration.py` | Create | New test suite with `TestMigrationServiceRealDb` class and tests |

## Interfaces / Contracts

```python
# Test setup pattern in tests/integration/test_migration.py
class TestMigrationServiceRealDb:
    def setup_method(self):
        self.adapter = WinComAdapter()
        assert self.adapter.connect(TEST_DB)
        self.service = MigrationService()

    def teardown_method(self):
        self.adapter.disconnect()
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Integration | Schema Extraction | Assert `ExtractedSchema` has `type_test`, correct columns, sizes, and nullability |
| Integration | Upload Schema | Assert `sqlite3` PRAGMA table_info returns mapped types (INTEGER, TEXT, REAL) |
| Integration | Transfer Data | Assert `sqlite3` `SELECT COUNT(*)` and `SELECT *` values match seed data |
| Integration | Idempotency | Extracting twice returns identical schema |
| Unit | Path resolution | `_find_connection_by_path` handles missing DBs and bad inputs |

## Migration / Rollout

No migration required. This is a testing change.

## Open Questions

- None