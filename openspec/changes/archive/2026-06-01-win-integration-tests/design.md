# Design: win-integration-tests

## Technical Approach

To achieve comprehensive integration test coverage for COM-based write operations without corrupting the master fixture, we will implement a file-level database cloning strategy. The master `test_db.accdb` fixture will be expanded to include complex objects (queries, forms, reports, VBA). Each destructive test will receive a fresh, temporary copy of this database. Tests will instantiate their own `WinComAdapter` pointing to the clone, execute the write operations, and cleanly disconnect, allowing the cloned file to be safely deleted during teardown.

## Architecture Decisions

### Decision: Fixture Object Creation Strategy

**Choice**: Use `LoadFromText` with minimal hardcoded text definitions in `generate_fixture.py` for UI objects (forms, reports, macros).
**Alternatives considered**: Using COM UI automation (`Application.CreateForm()`, `Application.CreateReport()`) or manually maintaining a binary `test_db.accdb` in version control.
**Rationale**: Access UI automation is flaky and requires visible windows or specific active states. Manually maintaining binary fixtures breaks version control diffs. `LoadFromText` is fast, invisible, and deterministically injects exactly the objects we need using the same serialization format the adapter relies on.

### Decision: Test Isolation Mechanism

**Choice**: File-level cloning using `shutil.copy2` into `tempfile.mkdtemp()` for every test.
**Alternatives considered**: DAO transactions with Rollback, or wiping/re-seeding tables within a single database.
**Rationale**: Access VBA and schema changes (DDL) cannot be reliably rolled back via transactions. Shared databases risk COM locking errors and state leakage. File-level cloning is the only guarantee of a pristine, isolated state for every test.

### Decision: COM Thread Management in Tests

**Choice**: Instantiate a fresh `WinComAdapter` per test class/method and rely on its internal `ComDispatcher` for STA thread management.
**Alternatives considered**: Sharing a single `WinComAdapter` and database connection across tests, or mocking the COM layer.
**Rationale**: Sharing connections risks cross-test contamination and orphaned `MSACCESS.EXE` processes if a test crashes. Reusing the production `ComDispatcher` ensures we test the exact lifecycle (start -> connect -> execute -> disconnect -> shutdown) used by the real MCP server.

## Data Flow

    Test Setup (conftest.py)      Test Execution                Test Teardown
    ───────────────────────       ──────────────                ─────────────
    1. Read TEST_DB path          4. Init WinComAdapter         7. adapter.disconnect()
    2. tempfile.mkdtemp()         5. connect(clone_path)           (closes COM/Access)
    3. shutil.copy2() ─────→      6. Execute write ops ─────→   8. rm -rf temp_dir
       Yield clone_path              Assert changes                (deletes clone)

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `tests/integration/generate_fixture.py` | Modify | Add `CreateQueryDef` for queries, and `LoadFromText` or VBA injection for forms, reports, and modules. |
| `tests/integration/conftest.py` | Create | Define `temp_db_copy` fixture for DB cloning and cleanup. |
| `tests/integration/test_wincom_data_write.py` | Create | Tests for `insert_data`, `update_data`, `delete_data`. |
| `tests/integration/test_wincom_table_query.py` | Create | Tests for `create_table`, `delete_table`, `create_query`, `set_query_sql`, `delete_query`. |
| `tests/integration/test_wincom_vba_write.py` | Create | Tests for `set_vba_code`, adding procedures, and VBA compilation checks. |
| `tests/integration/test_wincom_form_report.py` | Create | Tests for form/report export, property modification, and import. |
| `tests/integration/test_wincom_advanced.py` | Create | Tests for linked tables and launch/close lifecycle. |
| `tests/integration/test_mcp_tools_pool.py` | Modify | Update or add wrappers testing COM tools via `_call_tool()`. |

## Interfaces / Contracts

**Fixture Contract (`conftest.py`)**:
```python
@pytest.fixture
def temp_db_copy() -> Generator[str, None, None]:
    """Yields a path to a temporary copy of the test database."""
```

**Test Class Pattern**:
```python
@pytest.mark.com_integration
@skip_unless_windows
@skip_unless_pywin32
class TestWinComDataWrite:
    def setup_method(self, method):
        # Initialized manually in the test method to use the fixture
        pass
        
    def test_insert_data(self, temp_db_copy):
        adapter = WinComAdapter()
        assert adapter.connect(temp_db_copy)
        try:
            # act & assert
        finally:
            adapter.disconnect()
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Integration | Data CRUD | Call `insert/update/delete_data`, assert via `execute_query`. |
| Integration | Schema CRUD | Call `create/delete_table`, `create/delete_query`, assert via `get_tables()` and `get_queries()`. |
| Integration | VBA Lifecycle | Call `set_vba_code`, assert via `get_modules()` and code extraction. |
| Integration | UI Round-trip | Call `export_form_to_text`, modify text, `import_form_from_text`, assert `get_control_properties`. |

## Migration / Rollout

No data migration required. These are purely test-suite additions. The CI pipeline (if running Windows) will automatically pick up the new tests due to the existing `-m com_integration` markers.

## Open Questions

- None.
