# Delta for Text Export/Import Workflow

## ADDED Requirements

### Requirement: Module Backup Export

The system SHALL export a VBA module's code to a `.bas` file in a specified or default backup directory. The file SHALL use UTF-8 encoding and include a header with the module name and export timestamp.

#### Scenario: Export module to default backup dir

- GIVEN a connected COM database with module `mod_funcs`
- WHEN `export_module_backup("mod_funcs")` is called without `backup_dir`
- THEN a file `mod_funcs.bas` is created under `{tempdir}/ms_access_dev/backups/`
- AND the file contains the full VBA source code
- AND the response includes `backup_path`, `module_name`, and `file_size_bytes`

#### Scenario: Export module to custom backup dir

- GIVEN a connected COM database with module `mod_helpers`
- WHEN `export_module_backup("mod_helpers", "/tmp/my_backups")` is called
- THEN a file `mod_helpers.bas` is created under `/tmp/my_backups/`
- AND the directory is created if it does not exist

#### Scenario: Export non-existent module

- GIVEN a connected COM database
- WHEN `export_module_backup("nonexistent")` is called
- THEN the response has `success: false` with error `"Module 'nonexistent' not found"`

### Requirement: Module Import from Text File

The system SHALL delete the original module and import a replacement from a `.bas` file using `LoadFromText`. The system SHALL NOT import if the file does not exist.

#### Scenario: Import module from .bas file

- GIVEN a connected COM database with module `mod_funcs`
- WHEN `import_module_from_text("mod_funcs", "/tmp/edited/mod_funcs.bas")` is called
- THEN the original module `mod_funcs` is deleted
- AND the module is recreated from the `.bas` file content
- AND the response has `success: true`

#### Scenario: Import from non-existent file

- GIVEN a connected COM database
- WHEN `import_module_from_text("mod_funcs", "/tmp/missing.bas")` is called
- THEN the response has `success: false` with error containing "File not found"
- AND the original module is NOT deleted

### Requirement: Module Backup Restore

The system SHALL restore a module from a previously exported `.bas` backup file. This is a convenience wrapper over delete + import.

#### Scenario: Restore module from backup

- GIVEN a backup file `mod_funcs.bas` exists
- WHEN `restore_module_backup("mod_funcs", "/tmp/backups/mod_funcs.bas")` is called
- THEN the current module is deleted and replaced with the backup content
- AND the response has `success: true`

### Requirement: Form Backup Export

The system SHALL export a form (including VBA code-behind) to a `.txt` file using `SaveAsText`. The file SHALL use UTF-16-LE encoding matching Access's native format.

#### Scenario: Export form to default backup dir

- GIVEN a connected COM database with form `frmCustomers`
- WHEN `export_form_backup("frmCustomers")` is called
- THEN a file `frmCustomers.txt` is created under the default backup directory
- AND the response includes `backup_path` and `form_name`

#### Scenario: Export non-existent form

- GIVEN a connected COM database
- WHEN `export_form_backup("nonexistent")` is called
- THEN the response has `success: false` with error containing "not found"

### Requirement: Form Import from Text File

The system SHALL delete the original form and import a replacement from a `.txt` file using `LoadFromText`.

#### Scenario: Import form from .txt file

- GIVEN a connected COM database with form `frmCustomers`
- WHEN `import_form_from_text("frmCustomers", "/tmp/edited/frmCustomers.txt")` is called
- THEN the original form is deleted and recreated from the file
- AND the response has `success: true`

### Requirement: Form Backup Restore

The system SHALL restore a form from a previously exported `.txt` backup file.

#### Scenario: Restore form from backup

- GIVEN a backup file `frmCustomers.txt` exists
- WHEN `restore_form_backup("frmCustomers", "/tmp/backups/frmCustomers.txt")` is called
- THEN the current form is deleted and replaced with the backup content
- AND the response has `success: true`

### Requirement: Backup Directory Defaults

The system SHALL use `{tempdir}/ms_access_dev/backups/` as the default backup directory when `backup_dir` is not provided. The system SHALL create the directory if it does not exist.

#### Scenario: Default directory auto-creation

- GIVEN the default backup directory does not exist
- WHEN any export backup tool is called without `backup_dir`
- THEN the directory `{tempdir}/ms_access_dev/backups/` is created
- AND the backup file is written there
