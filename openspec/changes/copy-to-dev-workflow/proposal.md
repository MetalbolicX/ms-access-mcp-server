# Proposal: Copy-to-Dev Workflow

## Intent

VBA edits via COM (`set_vba_code`) are ephemeral — lost on disconnect. Users need a safe dev sandbox to iterate on VBA, forms, reports, and schema without risking production data. The goal: copy production DB to a temp location, edit freely, then deploy back with a safety backup.

## Scope

### In Scope
- `create_dev_copy` MCP tool — copy production DB to temp dir, switch connection
- `deploy_dev_copy` MCP tool — copy dev DB back to production (mandatory `.bak`)
- `discard_dev_copy` MCP tool — delete dev copy, reconnect to production
- `get_dev_copy_status` MCP tool — show dev copy state (active, paths, metadata)
- Manifest JSON tracking dev copies (production path, dev path, timestamps)
- Warnings: large DB (>500MB), linked tables may break

### Out of Scope
- Versioning / git-like history (covered by `versioning-export` spec)
- Concurrent multi-user edits (Access COM is single-instance)
- Text-based diff/merge of dev copies
- Rollback to specific versions
- User-configured dev copy location (V1 uses `tempfile.gettempdir()`)

## Capabilities

### New Capabilities
- `dev-copy-workflow`: Full lifecycle for dev copies — create, deploy, discard, status. Manages manifest tracking, disconnect/reconnect cycle, and safety backups.

### Modified Capabilities
- `com-automation`: Add `copy_database`, `disconnect`, `reconnect` operations to support the dev copy cycle.
- `access-mcp`: Register 4 new MCP tools in the server tool list.

## Approach

**Full Database Copy** using existing building blocks:

1. **Create**: `shutil.copy2(production_path, dev_path)` → disconnect production → connect to dev copy → write manifest JSON
2. **Edit**: All MCP tools (VBA, schema, data, forms, reports) operate on the dev copy transparently
3. **Deploy**: Disconnect dev → `shutil.copy2(dev_path, production_path)` with mandatory `.bak` of production first → reconnect production → update manifest
4. **Discard**: Disconnect dev → `os.remove(dev_path)` → reconnect production → remove manifest

Manifest file at `{tempdir}/ms_access_dev/{db_hash}.json`:
```json
{
  "production_path": "C:\\databases\\MyApp.accdb",
  "dev_path": "C:\\Users\\...\\AppData\\Local\\Temp\\ms_access_dev\\MyApp_dev.accdb",
  "created_at": "2026-05-24T13:00:00Z",
  "db_size_bytes": 52428800,
  "has_linked_tables": false
}
```

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/ms_access_mcp/adapters/base.py` | Modified | Add `copy_database`, dev-copy state to protocol |
| `src/ms_access_mcp/adapters/wincom.py` | Modified | Implement copy/disconnect/reconnect cycle |
| `src/ms_access_mcp/adapters/odbc.py` | Modified | Stub dev-copy methods (requires COM) |
| `src/ms_access_mcp/services/connection.py` | Modified | Track dev-copy state (production_path, dev_path, is_dev_mode) |
| `src/ms_access_mcp/services/dev_copy.py` | New | Dev copy manager: manifest CRUD, copy operations, warnings |
| `src/ms_access_mcp/mcp/server.py` | Modified | Register 4 new MCP tools |
| `tests/unit/test_dev_copy.py` | New | Unit tests for dev copy service |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Data loss on deploy (overwrite production) | Medium | Mandatory `.bak` backup before every deploy |
| Linked tables break in dev copy | Medium | Detect linked tables pre-copy, warn user |
| Large DB copy takes 30-60s (500MB+) | Low | Warn pre-copy, show file size |
| Access COM singleton blocks concurrent ops | Low | Already handled by STA thread serialization |
| Disk space exhaustion (double DB size) | Low | Warn on large DBs, cleanup on discard |

## Rollback Plan

1. If deploy corrupts production: restore from `.bak` file (same path, `.bak` extension)
2. If dev copy is broken: `discard_dev_copy` deletes it and reconnects to production (unchanged)
3. If feature is unwanted: remove the 4 MCP tools and `dev_copy.py` — no other code depends on them

## Dependencies

- `shutil.copy2` (stdlib) — already used in `compact_repair`
- `tempfile.gettempdir()` (stdlib) — already used in `_save_object_to_text`
- No new external packages

## Success Criteria

- [ ] `create_dev_copy` copies DB to temp dir and switches connection — edits persist across calls
- [ ] `deploy_dev_copy` creates `.bak` then overwrites production — production DB reflects all dev edits
- [ ] `discard_dev_copy` removes dev copy and reconnects to production — production untouched
- [ ] `get_dev_copy_status` returns accurate state when no copy, active copy, or error
- [ ] All 4 tools pass unit tests with mocked file operations
- [ ] Linked table warning fires when DB has ODBC/linked tables
- [ ] Large DB warning fires when DB > 500MB
