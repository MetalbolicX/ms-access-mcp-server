# Delta for win-com

## ADDED Requirements

### Requirement: Fixture Expansion (PR 1)
The system MUST provide an expanded test fixture that includes queries, forms, reports, macros, and VBA modules for integration testing.

#### Scenario: Generate comprehensive test database
- GIVEN a clean integration test run
- WHEN `generate_fixture.py` is executed
- THEN it generates a `test_db.accdb` containing tables (`customers`, `orders`, `products`)
- AND it contains query `qrySalesSummary`
- AND it contains forms (`frmMain`, `frmWithCode`)
- AND it contains report `rptCustomers`
- AND it contains VBA module `modUtilities`
- AND it contains macro `macTest`

### Requirement: Safety and Isolation (PR 1)
The system MUST isolate destructive COM write tests from the master test database to prevent state corruption.

#### Scenario: Execute destructive test safely
- GIVEN a test database fixture
- WHEN a test requiring write access executes
- THEN the system copies the database to a temporary directory
- AND the test mutates only the temporary clone
- AND the temporary clone is deleted during teardown
- AND the original test database remains unmodified

### Requirement: Data Write Operations (PR 1)
The system MUST correctly execute data insert, update, and delete operations via COM.

#### Scenario: Insert data
- GIVEN an isolated test database
- WHEN `insert` operation is called for `customers`
- THEN the new record is successfully added to the table

#### Scenario: Update data
- GIVEN an isolated test database with existing records
- WHEN `update` operation modifies an existing record
- THEN the record reflects the updated values

#### Scenario: Delete data
- GIVEN an isolated test database with existing records
- WHEN `delete` operation removes an existing record
- THEN the record is no longer present in the table

### Requirement: Schema Write Operations (PR 1)
The system MUST correctly execute table creation, table deletion, and query mutations via COM.

#### Scenario: Create and delete table
- GIVEN an isolated test database
- WHEN `create_table` is called
- THEN the new table exists in the database
- WHEN `delete_table` is called
- THEN the table is removed from the database

#### Scenario: Mutate query
- GIVEN an isolated test database
- WHEN a new query is created or an existing query's SQL is modified
- THEN the query reflects the new SQL definition

### Requirement: VBA Manipulation (PR 2)
The system MUST support reading and writing VBA module code, adding procedures, and deleting modules.

#### Scenario: Modify VBA code
- GIVEN an isolated test database containing `modUtilities`
- WHEN `set_vba_code` replaces the module content
- THEN the module contains the new code
- AND the code compiles without errors

#### Scenario: Add procedure
- GIVEN an isolated test database
- WHEN `add_vba_procedure` injects a new sub/function
- THEN the procedure is accessible in the module

#### Scenario: Delete module
- GIVEN an isolated test database
- WHEN `delete_module` is called
- THEN the VBA module is removed from the project

### Requirement: UI Component Round-trip (PR 2)
The system MUST successfully export, modify, and re-import Forms and Reports.

#### Scenario: Round-trip form
- GIVEN an isolated test database containing `frmMain`
- WHEN the form is exported to a text file
- AND the text file is modified
- AND the form is re-imported
- THEN the database contains the modified form definition

### Requirement: Advanced COM Testing (PR 3)
The system MUST execute advanced COM workflows including linked tables, dispatcher lifecycle, dev copies, and MCP tools safely.

#### Scenario: Test dispatcher lifecycle
- GIVEN a test requiring COM access
- WHEN the dispatcher initializes, executes a call, and shuts down
- THEN the COM connection is released cleanly
- AND no orphaned `MSACCESS.EXE` process remains

#### Scenario: Use MCP wrappers
- GIVEN an isolated test database
- WHEN MCP wrapper tools invoke write operations via COM
- THEN the operations execute successfully against the cloned DB