# Proposal: migration-sqlite-tests

## Intent

Close the integration test gap for migration tools by implementing end-to-end tests for `extract_schema`, `upload_schema`, and `transfer_data` using a real COM adapter and the SQLite target connector. This ensures the full migration pipeline works against real Access files.

## Scope

### In Scope
- Update `tests/integration/generate_fixture.py` to add seed data to existing tables.
- Add a new `type_test` table in the fixture covering Boolean, Date/Time, Currency, etc.
- Write `tests/integration/test_migration.py` with real `MigrationService`, `WinComAdapter`, and `SqliteConnector`.
- Implement test scenarios for extract, upload, transfer, idempotency, and round-trip type validation.
- Add isolation for `MigrationService` in test fixtures to prevent state leakage.

### Out of Scope
- Full CI integration (requires Windows CI with Access installed).
- End-to-end tests for non-SQLite connectors (PostgreSQL, MySQL, SQL Server).

## Capabilities

> This section is the CONTRACT between proposal and specs phases.
> The sdd-spec agent reads this to know exactly which spec files to create or update.

### New Capabilities
- None

### Modified Capabilities
- None

## Approach

1. Update the fixture generator (`generate_fixture.py`) to include realistic seed data and a table with all supported Access data types.
2. Write a new integration test file (`test_migration.py`) mirroring the structure of `test_real_adapter.py`.
3. Create test-scoped fixtures to instantiate a new `MigrationService` per test instead of using the global singleton, ensuring clean state.
4. Write tests that orchestrate the full migration pipeline: extract schema from the Access fixture, upload it to a temporary SQLite DB, transfer data, and query SQLite directly to assert rows and data types match.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `tests/integration/generate_fixture.py` | Modified | Add seed data and type-mapping table |
| `tests/integration/test_migration.py` | New | Integration tests for migration tools |
| `tests/integration/conftest.py` | Modified | Add migration service fixtures |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| COM dependency flakiness | Medium | Use robust setup/teardown with `try/finally` to release resources; skip if no Access |
| Global state in MigrationService | Medium | Instantiate new MigrationService per test instead of using the singleton |

## Rollback Plan

Revert changes to `generate_fixture.py` and delete `test_migration.py`.

## Dependencies

- Windows OS with MS Access/Access Database Engine installed for running the tests.
- `sqlite3` built-in module for target validation.

## Success Criteria

- [ ] Fixture generates successfully with seed data and the `type_test` table.
- [ ] `extract_schema` test passes with the real database.
- [ ] `upload_schema` creates correct SQLite tables.
- [ ] `transfer_data` correctly copies rows to SQLite and verifies count.
- [ ] Round-trip type validation succeeds for all tested types.
