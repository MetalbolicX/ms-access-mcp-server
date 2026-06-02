# Tasks: Copy-to-Dev Workflow

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~0 (already implemented) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Delivery strategy | single-pr |
| Chain strategy | N/A |

## Phase 1: Service Layer — DevCopyService

- [x] 1.1 Create `services/dev_copy.py` with manifest CRUD (`save_manifest`, `load_manifest`, `delete_manifest`).
- [x] 1.2 Implement `create_dev_copy()` — copies file, switches connection, writes manifest.
- [x] 1.3 Implement `deploy_dev_copy()` — creates `.bak`, overwrites production, updates manifest.
- [x] 1.4 Implement `discard_dev_copy()` — deletes dev file + manifest, reconnects production.
- [x] 1.5 Implement `get_dev_copy_status()` — returns dev copy state from manifest.

## Phase 2: Text Backup Pipeline

- [x] 2.1 Implement `export_module_backup()` — export VBA module to `.bas` file.
- [x] 2.2 Implement `import_module_from_text()` — delete module, recreate from `.bas`.
- [x] 2.3 Implement `restore_module_backup()` — delete + import from backup path.
- [x] 2.4 Implement `export_form_backup()` — export form to `.txt` via SaveAsText.
- [x] 2.5 Implement `import_form_from_file()` — delete form, recreate from `.txt`.
- [x] 2.6 Implement `restore_form_backup()` — delete + import from backup path.
- [x] 2.7 Implement `compile_with_retry()` helper for post-import compilation.
- [x] 2.8 Default backup dir: `{tempdir}/ms_access_dev/backups/`, auto-create if missing.

## Phase 3: Adapter Protocol Updates

- [x] 3.1 Add `copy_database(source, dest) -> bool` to `AccessAdapter` protocol in `base.py`.
- [x] 3.2 Implement `copy_database()` in `WinComAdapter` using `shutil.copy2`.
- [x] 3.3 Implement `copy_database()` stub in `OdbcAdapter` (returns `NotImplementedError`).
- [x] 3.4 Add `reconnect(new_path)` method to `ConnectionService`.

## Phase 4: MCP Tool Registration

- [x] 4.1 Create `mcp/dev_copy.py` with all 10 MCP tools (compact_repair, copy_database, 6 text pipeline, 4 dev copy).
- [x] 4.2 Register `compact_repair` tool.
- [x] 4.3 Register `copy_database` tool.
- [x] 4.4 Register text backup tools: `export_module_backup`, `import_module_from_text`, `restore_module_backup`, `export_form_backup`, `import_form_from_file`, `restore_form_backup`.
- [x] 4.5 Register dev copy tools: `create_dev_copy`, `deploy_dev_copy`, `discard_dev_copy`, `get_dev_copy_status`.

## Phase 5: Unit Tests

- [x] 5.1 Write `tests/unit/test_dev_copy.py` — MCP tool binding tests (connection guards, delegation to service).
- [x] 5.2 Write `tests/unit/test_dev_copy_service.py` — manifest CRUD, text pipeline, DB copy lifecycle, warnings, edge cases.
- [x] 5.3 All 50+ unit tests pass.

## Phase 6: Warnings & Edge Cases

- [x] 6.1 Large DB warning (>500 MB) on `create_dev_copy`.
- [x] 6.2 Linked tables warning on `create_dev_copy`.
- [x] 6.3 Error when creating dev copy while already in dev mode.
- [x] 6.4 Error when deploying/discarding with no active dev copy.
- [x] 6.5 `.bak` overwrite protection (old `.bak` is overwritten, not appended).
- [x] 6.6 Manifest JSON includes all required fields with ISO 8601 timestamps.
