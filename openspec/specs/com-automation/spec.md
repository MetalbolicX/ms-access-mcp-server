# COM Automation Specification

## Purpose

Manages the Access instance lifecycle and manipulates VBA objects via Windows COM.

## Requirements

### Requirement: Application Lifecycle

The system MUST be able to launch and close Microsoft Access instances invisibly or visibly.

#### Scenario: Launching Access invisibly
- GIVEN pywin32 is installed and running on Windows
- WHEN `launch_access(visible=false)` is called
- THEN an Access COM instance is created in the background

### Requirement: VBA Code Injection

The system MUST be able to read and write VBA code to modules.

#### Scenario: Setting VBA code
- GIVEN a running COM instance with a database open
- WHEN `set_vba_code` is called with module name and code string
- THEN the system overwrites the module's code component with the new string

#### Scenario: Trust center restriction
- GIVEN the Access Trust Center does not allow VBA object model access
- WHEN `set_vba_code` is called
- THEN the system catches the COM error and returns a clear message instructing the user to enable Trust Center access