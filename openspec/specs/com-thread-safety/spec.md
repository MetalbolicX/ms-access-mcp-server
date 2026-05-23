# COM Thread Safety Specification

## Purpose

Ensure all WinComAdapter COM operations execute on a single dedicated STA thread, eliminating thread-affinity failures that cause intermittent "Not connected" errors in async MCP server environments.

## Requirements

### Requirement: COM Object Thread Ownership

The system MUST execute all COM operations against the Access.Application object on a single dedicated STA thread, regardless of which async worker thread handles the incoming request.

#### Scenario: COM operation on same thread
- GIVEN a WinComAdapter is connected to a database
- WHEN any adapter method that touches COM is called from any async worker thread
- THEN the operation executes on the dedicated STA thread and returns the result to the caller

#### Scenario: Multiple rapid sequential calls
- GIVEN a WinComAdapter is connected
- WHEN `connect_access`, then `get_tables`, then `execute_sql_script` are called in rapid succession from different MCP sessions/threads
- THEN all three operations execute sequentially on the same STA thread without thread-affinity errors

### Requirement: Thread Dispatcher Lifecycle

The system MUST initialize the COM dispatcher when the first COM operation occurs and cleanly shut it down when `disconnect()` is called.

#### Scenario: Lazy dispatcher initialization
- GIVEN no adapter method has been called yet
- WHEN `connect_access` is called
- THEN the system creates a new STA thread, initializes COM, and dispatches the connection call through it

#### Scenario: Clean disconnect and dispatcher shutdown
- GIVEN a WinComAdapter is connected
- WHEN `disconnect()` is called
- THEN the system closes the Access.Application COM object, terminates the STA thread, and clears all adapter state

### Requirement: Timeout and Error Handling

The system MUST time out COM operations that block beyond a reasonable threshold to prevent deadlocks.

#### Scenario: COM operation times out
- GIVEN a COM operation is in progress on the dispatcher thread
- WHEN the operation takes longer than 30 seconds
- THEN the caller's Future.result() raises a TimeoutError and the dispatcher continues processing queued requests

#### Scenario: COM operation raises exception
- GIVEN a COM operation in progress raises an exception
- WHEN the exception propagates through the dispatcher
- THEN the exception is captured and re-raised to the caller via Future.set_exception()

### Requirement: Platform Isolation

The system MUST NOT attempt COM operations on non-Windows platforms.

#### Scenario: Adapter instantiated on Linux
- GIVEN `WinComAdapter()` is instantiated on a non-Windows platform
- WHEN any method is called that would normally use the dispatcher
- THEN the method returns an appropriate error indicating COM is unavailable on this platform