# Proposal: win-integration-tests

## Intent

To establish a comprehensive Windows-side integration test suite for the `WinComAdapter`. Currently, the integration test suite only covers read operations because destructive operations require a safe, isolated database environment. By expanding the fixture generation and introducing isolated test instances, we can validate critical write operations (Data, Schema, VBA, and UI components) against a real Microsoft Access instance via COM automation.

## Scope

### In Scope
- Expanding `generate_fixture.py` to create forms, reports, VBA modules, saved queries, macros, and linked tables.
- Adding tests for P0 data/schema modifications: insert, update, delete, create table, delete table, create/set/delete query, and their MCP wrappers.
- Adding tests for VBA modifications: set_vba_code, add_vba_procedure, delete_module.
- Adding tests for P1 UI operations: Form/Report import/export, control property mutations, and event procedure retrieval.
- Implementing a safe teardown fixture (`tempfile` + `shutil.copy2`) for destructive tests.
- Enforcing `com_integration` markers and sequential `-n 0` execution rules.

### Out of Scope
- Cross-platform tests (these features are Windows-only by design).
- Tests for P2 features like HTTP transport E2E, Trusted Locations winreg, or dev copy pipeline (unless trivial to include).
- Modifications to `OdbcAdapter` write operations, focusing strictly on COM.

## Capabilities

### New Capabilities
- `win-com-data-write`: Tests for data mutation via COM (insert, update, delete).
- `win-com-schema-write`: Tests for table creation/deletion and query mutations.
- `win-com-vba-write`: Tests for VBA code manipulation and module lifecycle.
- `win-com-ui-write`: Tests for Forms, Reports, and Control property/event manipulation.

### Modified Capabilities
- `fixture-generation`: Expanding the Access DB generator to contain complex database objects.

## Approach

We will enhance `generate_fixture.py` by adding VBA/COM instructions to inject forms, reports, and modules into `test_db.accdb` during its creation. In `test_real_adapter.py`, we will introduce a new Pytest fixture (e.g., `cloned_db`) that uses `shutil.copy2` to duplicate the test database to a temporary directory before each destructive test and cleans it up afterward. New test classes will be added to cover Data CRUD, Schema CRUD, VBA, and UI manipulation, all appropriately marked with `@pytest.mark.com_integration` and `skip_unless_windows`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `tests/integration/generate_fixture.py` | Modified | Add logic to create queries, forms, reports, macros, and VBA modules. |
| `tests/integration/test_real_adapter.py` | Modified | Add test classes for write operations utilizing temporary DB clones. |
| `tests/integration/helpers.py` | Modified | Potential minor additions for test clone setup/teardown. |
| `tests/integration/test_mcp_tools_pool.py` | Modified | Add or update tests ensuring MCP tool wrappers correctly handle write actions over COM. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Destructive tests mutate master fixture | High | Use `tempfile.mkdtemp` and `shutil.copy2` to isolate databases per test. |
| Parallel test execution deadlocks Access COM | High | Ensure COM tests run sequentially, utilizing the `com_integration` marker and standard configurations. |
| Orphaned `MSACCESS.EXE` processes | Medium | Rely on `ComDispatcher._release_com_safe()` cleanup routines and wrap tests in try/finally blocks. |

## Rollback Plan

Revert the modifications to the test files (`generate_fixture.py`, `test_real_adapter.py`, `helpers.py`, etc.). Since this change only impacts the test suite and not the production application code, rolling back is completely safe and isolated.

## Success Criteria

- [ ] `generate_fixture.py` successfully creates an Access database containing tables, queries, forms, reports, macros, and VBA modules.
- [ ] Destructive tests (Data, Schema, VBA) pass locally on Windows without altering the master `test_db.accdb` file.
- [ ] P0 (Critical) write operations for data, table, query, and VBA are fully covered.
- [ ] P1 (Important) UI and Control modification tests pass.
- [ ] Orphaned `MSACCESS.EXE` processes are not left running after test completion.
