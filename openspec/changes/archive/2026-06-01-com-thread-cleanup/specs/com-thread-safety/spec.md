# Delta for com-thread-safety

## MODIFIED Requirements

### Requirement: Thread Dispatcher Lifecycle

The system MUST initialize the COM dispatcher when the first COM operation occurs and cleanly shut it down when `disconnect()` is called.

#### Scenario: Clean disconnect with ordered release
- GIVEN a WinComAdapter is connected with an active ADO connection, DAO database, and Access Application
- WHEN `disconnect()` is called
- THEN the system releases COM objects in strict order: ADO Close() → DAO Close() → CloseCurrentDatabase() → Application.Quit()
- AND the STA thread terminates after cleanup completes
- AND all adapter state (`_access_app`, `_current_db`, `_ado_conn`, `_db_path`) is set to None
(Previously: "closes the Access.Application COM object" without specifying release order or guaranteeing completeness)

## ADDED Requirements

### Requirement: Force-Kill Fallback

If `Application.Quit()` fails or takes longer than 5 seconds, the system MUST terminate MSACCESS.EXE via `taskkill /F /IM MSACCESS.EXE`.

#### Scenario: Quit() times out
- GIVEN the Access Application is unresponsive
- WHEN `Quit()` does not complete within 5 seconds
- THEN the watchdog timer fires
- AND `taskkill /F /IM MSACCESS.EXE` is executed
- AND `_access_app` is set to None

#### Scenario: Quit() succeeds normally
- GIVEN the Access Application responds to `Quit()`
- WHEN `Quit()` completes within 5 seconds
- THEN force-kill is NOT executed
- AND `_access_app` is set to None

### Requirement: No Orphaned COM Objects

The system MUST release all COM references after every disconnect and shutdown path, leaving no orphaned `MSACCESS.EXE` process.

#### Scenario: Server shutdown
- GIVEN the server is shutting down via `shutdown()`
- WHEN the STA thread join completes
- THEN `_access_app`, `_current_db`, and `_ado_conn` are all None
- AND no MSACCESS.EXE process remains

#### Scenario: Connect failure after COM creation
- GIVEN `connect()` opens COM objects but fails during OpenCurrentDatabase
- WHEN the exception handler runs
- THEN `_release_com_safe()` is called
- AND no orphaned COM objects remain

### Requirement: Cleanup Error Logging

All cleanup errors MUST be printed to stderr and MUST NOT be silently swallowed with bare `pass`.

#### Scenario: ADO Close fails
- GIVEN `_ado_conn.Close()` raises an exception during cleanup
- WHEN the exception is caught
- THEN `f"Cleanup warning: _ado_conn.Close() failed: {e}"` is printed to stderr
- AND cleanup continues to the DAO Close step

#### Scenario: All cleanup steps fail
- GIVEN every step in the cleanup sequence raises an exception
- WHEN cleanup completes
- THEN each error is logged individually with its step name
- AND force-kill is attempted as final fallback

### Requirement: Platform-Guarded Force-Kill

The force-kill fallback MUST only execute on Windows platforms (`sys.platform == 'win32'`).

#### Scenario: Force-kill on Windows
- GIVEN `sys.platform == 'win32'`
- WHEN `Quit()` times out
- THEN `subprocess.run(["taskkill", "/F", "/IM", "MSACCESS.EXE"])` is called

#### Scenario: Force-kill on non-Windows
- GIVEN `sys.platform != 'win32'`
- WHEN `Quit()` fails
- THEN force-kill is skipped
- AND a warning is logged: "Cleanup warning: taskkill only supported on Windows"
