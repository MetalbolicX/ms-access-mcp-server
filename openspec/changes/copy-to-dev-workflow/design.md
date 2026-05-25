# Design: Copy-to-Dev Workflow (Hybrid Approach)

## Technical Approach

Two complementary pipelines sharing a common backup directory and connection lifecycle:

1. **Text Export/Import Pipeline** — lightweight, per-object backup/restore using Access `SaveAsText`/`LoadFromText` for VBA modules, forms, reports, and macros. No full DB copy needed.
2. **Full DB Copy Pipeline** — `shutil.copy2` of the entire `.accdb` to a temp dev sandbox for schema changes (tables, relationships). Disconnect/reconnect cycle through `ConnectionService`.

Both pipelines are COM-only (WinComAdapter). OdbcAdapter gets stubs returning `NotImplementedError`.

## Architecture Decisions

### Decision: Separate DevCopyService vs inline in ConnectionService

**Choice**: New `DevCopyService` class in `services/dev_copy.py`, injected into MCP tools alongside `ConnectionService`.

**Alternatives considered**: Embed dev copy state directly into `ConnectionService`.

**Rationale**: `ConnectionService` already manages connection lifecycle. Adding copy logic, manifest CRUD, and warnings would violate single responsibility. `DevCopyService` owns manifest + file operations; `ConnectionService` owns connect/disconnect. They collaborate: `DevCopyService` calls `ConnectionService.disconnect()` / `.connect()`.

### Decision: Manifest location and hashing

**Choice**: Manifest at `{tempdir}/ms_access_dev/{hashlib.md5(production_path.encode()).hexdigest()[:8]}.json`. Short hash avoids collisions for different DBs while keeping paths readable.

**Alternatives considered**: Full MD5 hash, UUID-based naming, single manifest for all DBs.

**Rationale**: Short hash is readable and collision-safe for typical usage (few DBs). Single manifest would create conflicts if multiple DBs are edited concurrently (unlikely but possible via separate MCP sessions).

### Decision: Text export uses existing `_save_object_to_text` / `_load_object_from_text`

**Choice**: Reuse the existing private methods in `WinComAdapter` for SaveAsText/LoadFromText. New adapter methods `export_object_backup` and `import_object_from_file` wrap these with file I/O.

**Alternatives considered**: New standalone functions, duplicating SaveAsText logic.

**Rationale**: The adapter already has `_save_object_to_text(object_type, name) -> str` and `_load_object_from_text(object_type, name, text_data) -> bool`. We add file-based wrappers that handle backup dir creation, file writing, and return structured dicts. No logic duplication.

### Decision: Backup directory default

**Choice**: `{tempfile.gettempdir()}/ms_access_dev/backups/` for text exports, `{tempfile.gettempdir()}/ms_access_dev/` for DB copies.

**Alternatives considered**: User's home dir, project-relative `.backups/`, same dir as production DB.

**Rationale**: Temp dir is always writable, auto-cleaned by OS, already used by `_save_object_to_text`. Separating `backups/` (text files) from root (DB copies) avoids confusion.

## Data Flow

### Text Export/Import Pipeline

```
MCP Tool (export_module_backup)
  → DevCopyService.export_module_backup(adapter, module_name, backup_dir?)
    → adapter.export_module_to_text(module_name)  [existing]
    → write .bas file to backup_dir
    → return {success, backup_path, file_size_bytes}

MCP Tool (import_module_from_text)
  → DevCopyService.import_module_from_file(adapter, module_name, file_path)
    → read .bas file
    → adapter.delete_form equivalent for modules (VBComponents.Remove)
    → adapter._load_object_from_text(5, module_name, content)
    → return {success}

MCP Tool (restore_module_backup)
  → DevCopyService.restore_from_backup(adapter, "module", module_name, backup_path)
    → delete + import (same as import but from backup path)
```

### Full DB Copy Pipeline

```
MCP Tool (create_dev_copy)
  → DevCopyService.create_dev_copy(conn_service, adapter, backup_dir?)
    → check not already in dev mode (read manifest)
    → get DB file size, detect linked tables (warnings)
    → shutil.copy2(production_path, dev_path)
    → conn_service.disconnect()
    → conn_service.connect(dev_path, adapter)
    → write manifest JSON
    → return {success, dev_path, production_path, warnings}

MCP Tool (deploy_dev_copy)
  → DevCopyService.deploy_dev_copy(conn_service, adapter)
    → read manifest (fail if none)
    → conn_service.disconnect()
    → shutil.copy2(production_path, production_path + ".bak")  [mandatory backup]
    → shutil.copy2(dev_path, production_path)
    → conn_service.connect(production_path, adapter)
    → update manifest with deployed_at
    → return {success, backup_path}

MCP Tool (discard_dev_copy)
  → DevCopyService.discard_dev_copy(conn_service, adapter)
    → read manifest (fail if none)
    → conn_service.disconnect()
    → os.remove(dev_path)
    → os.remove(manifest_path)
    → conn_service.connect(production_path, adapter)
    → return {success, reconnected_to}
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/ms_access_mcp/services/dev_copy.py` | **Create** | `DevCopyService`: manifest CRUD, text export/import wrappers, DB copy operations, warnings |
| `src/ms_access_mcp/adapters/base.py` | **Modify** | Add `copy_database(source, dest)` to `AccessAdapter` protocol |
| `src/ms_access_mcp/adapters/wincom.py` | **Modify** | Implement `copy_database` (shutil.copy2), add `export_object_to_file` / `import_object_from_file` |
| `src/ms_access_mcp/adapters/odbc.py` | **Modify** | Stub `copy_database` returning `NotImplementedError` |
| `src/ms_access_mcp/services/connection.py` | **Modify** | Add `reconnect(new_path)` method for seamless path switching |
| `src/ms_access_mcp/mcp/server.py` | **Modify** | Register 10 new MCP tools (6 text pipeline + 4 dev copy) |
| `tests/unit/test_dev_copy.py` | **Create** | Unit tests for DevCopyService with mocked adapter and file ops |
| `tests/unit/test_text_backup.py` | **Create** | Unit tests for text export/import backup tools |

## Interfaces / Contracts

### DevCopyService

```python
class DevCopyService:
    def __init__(self, backup_dir: str | None = None):
        self._backup_dir = backup_dir or os.path.join(tempfile.gettempdir(), "ms_access_dev", "backups")
        self._dev_dir = os.path.join(tempfile.gettempdir(), "ms_access_dev")

    # Text pipeline
    def export_module_backup(self, adapter: AccessAdapter, module_name: str, backup_dir: str | None = None) -> dict: ...
    def import_module_from_file(self, adapter: AccessAdapter, module_name: str, file_path: str) -> dict: ...
    def restore_module_backup(self, adapter: AccessAdapter, module_name: str, backup_path: str) -> dict: ...
    def export_form_backup(self, adapter: AccessAdapter, form_name: str, backup_dir: str | None = None) -> dict: ...
    def import_form_from_file(self, adapter: AccessAdapter, form_name: str, file_path: str) -> dict: ...
    def restore_form_backup(self, adapter: AccessAdapter, form_name: str, backup_path: str) -> dict: ...

    # DB copy pipeline
    def create_dev_copy(self, conn_service: ConnectionService, adapter: AccessAdapter, backup_dir: str | None = None) -> dict: ...
    def deploy_dev_copy(self, conn_service: ConnectionService, adapter: AccessAdapter) -> dict: ...
    def discard_dev_copy(self, conn_service: ConnectionService, adapter: AccessAdapter) -> dict: ...
    def get_dev_copy_status(self) -> dict: ...

    # Internal
    def _read_manifest(self) -> dict | None: ...
    def _write_manifest(self, data: dict) -> None: ...
    def _delete_manifest(self) -> None: ...
    def _get_db_hash(self, db_path: str) -> str: ...
    def _check_linked_tables(self, adapter: AccessAdapter) -> tuple[bool, int]: ...
    def _get_db_size(self, db_path: str) -> int: ...
```

### Manifest JSON Schema

```json
{
  "production_path": "C:\\databases\\MyApp.accdb",
  "dev_path": "C:\\Users\\...\\AppData\\Local\\Temp\\ms_access_dev\\a1b2c3d4\\MyApp_dev.accdb",
  "created_at": "2026-05-24T13:00:00Z",
  "db_size_bytes": 52428800,
  "has_linked_tables": false,
  "linked_table_count": 0,
  "deployed_at": null
}
```

### ConnectionService.reconnect

```python
def reconnect(self, new_path: str) -> bool:
    """Disconnect and reconnect to a different database path using the same adapter."""
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `DevCopyService` manifest CRUD | Mock file ops, verify JSON structure |
| Unit | Text export/import wrappers | Mock adapter methods, verify file I/O |
| Unit | DB copy create/deploy/discard | Mock `shutil.copy2`, `os.remove`, verify disconnect/reconnect calls |
| Unit | Warnings (large DB, linked tables) | Mock `os.path.getsize` and `get_linked_tables` |
| Unit | Edge cases: no dev copy, already in dev mode | Verify error responses |
| Integration | Full lifecycle: create → edit → deploy | Requires Windows + Access (CI skip) |

## Migration / Rollout

No migration required. New tools are additive — no existing behavior changes. Feature is opt-in (user must call `create_dev_copy` explicitly).

## Open Questions

- [ ] Should `import_module_from_text` support importing into a NEW module (currently requires module to exist)? Proposal says "deletes original module, imports" — implies it must exist first. Consider `add_vba_procedure` as fallback.
- [ ] Should `deploy_dev_copy` validate that the dev DB is not corrupt before overwriting production? (e.g., try opening it first)
