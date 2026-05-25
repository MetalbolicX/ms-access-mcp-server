# Delta for Dev Copy Workflow

## ADDED Requirements

### Requirement: Create Dev Copy

The system SHALL copy the entire production `.accdb` file to a temp directory, disconnect from production, connect to the dev copy, and write a manifest JSON tracking the dev session.

#### Scenario: Create dev copy successfully

- GIVEN a connected COM database at `C:\databases\MyApp.accdb`
- WHEN `create_dev_copy()` is called
- THEN the file is copied to `{tempdir}/ms_access_dev/{db_hash}/MyApp_dev.accdb`
- AND the connection switches to the dev copy
- AND a manifest JSON is written with `production_path`, `dev_path`, `created_at`, `db_size_bytes`, `has_linked_tables`
- AND the response includes `dev_path`, `production_path`, and `db_size_bytes`

#### Scenario: Create dev copy with custom backup dir

- GIVEN a connected COM database
- WHEN `create_dev_copy("/tmp/my_dev")` is called
- THEN the file is copied to `/tmp/my_dev/MyApp_dev.accdb`
- AND the manifest is written there

#### Scenario: Create dev copy when already in dev mode

- GIVEN the system is already in dev copy mode
- WHEN `create_dev_copy()` is called
- THEN the response has `success: false` with error "Dev copy already active"
- AND the existing dev copy is NOT overwritten

#### Scenario: Large database warning

- GIVEN a connected database larger than 500 MB
- WHEN `create_dev_copy()` is called
- THEN the response includes `warning: "Database is {size} MB. Copy may take 30-60 seconds."`
- AND the copy proceeds (warning is informational, not blocking)

#### Scenario: Linked tables warning

- GIVEN a connected database with linked tables
- WHEN `create_dev_copy()` is called
- THEN the response includes `warning: "Database has N linked tables. Links may break in dev copy."`
- AND the copy proceeds

### Requirement: Deploy Dev Copy

The system SHALL copy the dev DB back to the production path with a mandatory `.bak` backup of the original production file, then reconnect to production.

#### Scenario: Deploy dev copy to production

- GIVEN an active dev copy at `/tmp/dev/MyApp_dev.accdb` with production at `C:\databases\MyApp.accdb`
- WHEN `deploy_dev_copy()` is called
- THEN the production file is backed up to `C:\databases\MyApp.accdb.bak`
- AND the dev copy is copied over the production file
- AND the connection switches to the production file
- AND the manifest is updated with `deployed_at` timestamp
- AND the response includes `production_path`, `backup_path`

#### Scenario: Deploy when no dev copy active

- GIVEN no active dev copy
- WHEN `deploy_dev_copy()` is called
- THEN the response has `success: false` with error "No active dev copy"

#### Scenario: Deploy with existing .bak file

- GIVEN a `.bak` file already exists at the production backup path
- WHEN `deploy_dev_copy()` is called
- THEN the existing `.bak` is overwritten with the current production file
- AND the deploy proceeds normally

### Requirement: Discard Dev Copy

The system SHALL delete the dev copy file, remove the manifest, and reconnect to the original production database.

#### Scenario: Discard dev copy

- GIVEN an active dev copy
- WHEN `discard_dev_copy()` is called
- THEN the dev copy file is deleted
- AND the manifest file is deleted
- AND the connection switches back to the production path
- AND the response has `success: true` with `reconnected_to: production_path`

#### Scenario: Discard when no dev copy active

- GIVEN no active dev copy
- WHEN `discard_dev_copy()` is called
- THEN the response has `success: false` with error "No active dev copy"

### Requirement: Dev Copy Status

The system SHALL return the current dev copy state including whether a dev copy is active, paths, timestamps, and warnings.

#### Scenario: Status with active dev copy

- GIVEN an active dev copy with manifest
- WHEN `get_dev_copy_status()` is called
- THEN the response includes `is_dev_mode: true`, `production_path`, `dev_path`, `created_at`, `db_size_bytes`, `has_linked_tables`

#### Scenario: Status with no dev copy

- GIVEN no active dev copy
- WHEN `get_dev_copy_status()` is called
- THEN the response includes `is_dev_mode: false`

### Requirement: Manifest Tracking

The system SHALL maintain a JSON manifest file at `{tempdir}/ms_access_dev/{db_hash}.json` that tracks the dev copy lifecycle. The manifest SHALL include `production_path`, `dev_path`, `created_at`, `db_size_bytes`, and `has_linked_tables`.

#### Scenario: Manifest created on dev copy

- GIVEN `create_dev_copy()` succeeds
- THEN a JSON file is written with all required fields
- AND `created_at` is an ISO 8601 timestamp

#### Scenario: Manifest updated on deploy

- GIVEN `deploy_dev_copy()` succeeds
- THEN the manifest is updated with `deployed_at` timestamp
- AND the manifest file is preserved for audit trail

#### Scenario: Manifest deleted on discard

- GIVEN `discard_dev_copy()` succeeds
- THEN the manifest JSON file is deleted
