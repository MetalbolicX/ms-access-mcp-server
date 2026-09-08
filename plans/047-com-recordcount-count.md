# Plan 047: Populate recordCount via SELECT COUNT(*) in the COM adapter

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**:
> `git diff --stat 016ebdb..HEAD -- rescript-mcp/src/Adapters/ComDataAdapter.res rescript-mcp/test/ComDdlTest.res`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED (adds COM recordset traffic inside the TableDefs loop — crash-adjacent until plan 045 lands)
- **Depends on**: plan 045 for **verification** (the `get_tables` / `get_table_schema` cases exit-134 intermittently until then). The implementation itself is independent.
- **Category**: bug
- **Planned at**: commit `016ebdb`, 2026-09-07

## Why this matters

Python's oracle returns the real row count per table (`recordCount: 5` for Customers in the northwind fixture). The ReScript COM adapter hard-codes `recordCount: 0` in `_getTablesImpl`. Even once plan 045 stops the teardown crashes, `get_tables` and `get_table_schema-Customers` will FAIL on `recordCount` until this lands. It is a latent mismatch: invisible while crashes mask it, blocking the moment they're gone.

## Current state

### Python oracle — `src/ms_access_mcp/adapters/schema_inspector.py:101-108` (inside `get_tables._do`)

```python
101:                    record_count = 0
102:                    try:
103:                        rs = db.OpenRecordset(f"SELECT COUNT(*) FROM [{tdef.Name}]")
104:                        if not rs.EOF:
105:                            record_count = rs.Fields(0).Value
106:                        rs.Close()
107:                    except Exception:
108:                        pass
```

Note: opened **while iterating TableDefs** (same loop), failure tolerated → 0. The snake_case envelope key comes from `src/ms_access_mcp/mcp/schema.py:166` (`"record_count": table.record_count`) — the parity normalizer handles the camelCase/snake_case mapping (existing `get_tables.json` case passes on ODBC where recordCount is real, so the differ is already key-compatible).

**Important**: `get_system_tables` (`schema_inspector.py:125-152`) does NOT count — it always returns `record_count=0`. Only the user-table path counts.

### ReScript COM site — `rescript-mcp/src/Adapters/ComDataAdapter.res`, `_getTablesImpl` (starts `:1112`)

Two hard-coded zeros in the table-push branches:

```rescript
1195-1198:  (systemOnly branch — the isSystem push)
              name: name,
              fields: fieldsArr,
              recordCount: 0,        // ← stays 0 (matches python get_system_tables)
1215-1218:  (user-table branch — the !isSystem push)
              name: name,
              fields: fieldsArr,
              recordCount: 0,        // ← THIS one must become COUNT(*)
```

### ReScript envelope passthrough — already correct

- `Facade.res:664` (getTables) and `Facade.res:719` (getTableSchema): `Dict.set(d, "recordCount", JSON.Number(Int.toFloat(t.recordCount)))` — no facade change needed.

### In-repo conventions to copy

- **ODBC COUNT idiom**: `OdbcAdapter.res:709-711` (`_buildCountQuery`: `"SELECT COUNT(*) FROM [" ++ tableName ++ "]"`) with graceful degradation to 0 on failure (`:773-777`).
- **COM recordset idiom**: `_executeQueryImpl` (`ComDataAdapter.res:404-461`) — the OpenRecordset → Fields → MoveNext → close pattern.
- **Recordset close helper**: `_closeRecordset` (`ComDataAdapter.res:231-243`) — invoke + Close then release, error-tolerant. Plan 045 converts its releases to `releaseSyncAwait`; whatever it is when you start, use it as-is.
- **Release discipline**: plan 043's maintenance note — any NEW release of a real COM handle in your code must use `releaseSyncAwait` (or the helper that already does).

### Expected values (northwind fixture, `db/northwind.accdb`)

From the Python artifact (`parity/runs/run-1788833705405-zj8ofe2/get_table_schema-Customers-python.json`): Customers → `recordCount: 5`, 11 fields. Tables in the fixture: Categories, Customers, Employees, Orders, Products, Shippers, Suppliers, Order Details (8 tables).

### Existing tests

- `ComDdlTest.res` contains the real-COM tests that call `getTables` (e.g. the ComIntegration family). Grep for `recordCount` in `rescript-mcp/test/` before changing anything and update any assertion that pins `0` for a user table.
- `FacadeTest.res` fakes return canned `tableInfo` values — unaffected.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Build | `pnpm -C rescript-mcp build` | exit 0 |
| Unit suite | `pnpm -C rescript-mcp test` | 827 tests, 0 failed |
| Fixture setup | `Copy-Item db\northwind.accdb tests\integration\fixtures\test_db.accdb -Force` | file exists |
| Single-case parity | see plan 045 "Commands" (`--case=get_table_schema-Customers.json`, then `--case=get_tables.json`, read-only cases-dir) | `PASS` (requires plan 045 landed) |

Pre-run hygiene (before every parity run):

```powershell
Get-Process MSACCESS -ErrorAction SilentlyContinue | Stop-Process -Force
Remove-Item tests\integration\fixtures\*.laccdb, db\*.laccdb -ErrorAction SilentlyContinue
```

## Scope

**In scope**:

- `rescript-mcp/src/Adapters/ComDataAdapter.res` — new `_countRecords` helper + the user-table branch of `_getTablesImpl`
- `rescript-mcp/test/ComDdlTest.res` — one new real-COM assertion + any `recordCount: 0` pins for user tables
- `rescript-mcp/parity/findings.md`, `plans/README.md` — recording

**Out of scope**:

- The `systemOnly` branch (`:1195`) — python's `get_system_tables` hard-codes 0; parity demands 0 there
- `_getTableSchemaPlanImpl` — different shape (migration plan), python's COUNT there is internal and not envelope-visible
- `generateSql` / `getDatabaseStatistics` internals
- ODBC adapter (already counts)
- Facade shapers (already pass recordCount through)

## Git workflow

- Branch: `rescript/047-com-recordcount`
- Commit style: `feat(parity): COM getTables populates recordCount via SELECT COUNT(*)`
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Add the `_countRecords` helper

Place it inside the `DaoAdapter` module just above `_getTablesImpl` (near `:1112`), modeled on the `_executeQueryImpl` idiom and `_closeRecordset`:

```rescript
// Plan 047: record count for a user table, mirroring python
// schema_inspector.py:101-108 — COUNT(*) recordset, tolerant of failure (→ 0).
let _countRecords = (db: ComInterfaces.comObject, tableName: string): Promise.t<int> => {
  let sql = "SELECT COUNT(*) FROM [" ++ tableName ++ "]"
  // invoke(db, "OpenRecordset", [VStr(sql)]) — copy the exact variant-wrapping
  // style used by _executeQueryImpl for string args; then:
  //   on Error(_)            → Promise.resolve(0)
  //   on Ok(rs)              → read rs "Fields" → getItem(VInt(0)) → get "Value"
  //                             (copy the field-read chain from _executeQueryImpl)
  //   coerce JSON.Number(n)  → n->Float.toInt ; anything else → 0
  //   finally _closeRecordset(rs) before resolving (error-tolerant already)
}
```

The sketch above is intentionally not copy-pasteable — the variant constructors (`VStr`/`VInt`) and envelope-wrapping (`%raw("v => ({ __p__: v })")`) must match how `_executeQueryImpl` does it; read that function first and mirror it exactly. The `db` handle is already in scope inside `_getTablesImpl` (from `ComSession.getCurrentDb(session)`), so the helper takes `db` directly — do NOT go through `self`.

**Verify**: `pnpm -C rescript-mcp build` → exit 0 (function unused is fine for now; if the compiler warns about unused, continue — it gets used in Step 2).

### Step 2: Wire it into the user-table branch of `_getTablesImpl`

In the `!isSystem` push branch (`:1215` area), replace `recordCount: 0` with the counted value:

```rescript
_enumerateTableFields(td)
->Promise.then(fieldsArr =>
  _countRecords(db, name)          // ← insert; `db` and `name` in scope
  ->Promise.then(recordCount => {
      let ti: Interfaces.tableInfo = {
        name: name,
        fields: fieldsArr,
        recordCount: recordCount,
        primaryKey: None,
      }
      ...
```

Keep the `systemOnly` branch (`:1195`) at `recordCount: 0`.

**Verify**:
1. `pnpm -C rescript-mcp build` → exit 0
2. `pnpm -C rescript-mcp test` → if a real-COM test that reads a user table now sees nonzero counts and fails on a `0` pin, update that assertion to `>= 0` semantics or the exact expected count for its fixture table (prefer exact when the fixture is deterministic). Suite must end 827-equivalent (count may grow in Step 3), 0 failed.

### Step 3: Add a real-COM regression test

In `ComDdlTest.res`, add one test modeled on the neighboring ComIntegration tests (copy their session setup/teardown scaffolding verbatim — including EBUSY-tolerant file cleanup where present): connect to the fixture copy, `getTables()`, find `Customers`, assert `recordCount == 5` and `fields` length `== 11`. Follow the existing naming pattern (`ComIntegration: ...`).

**Verify**: `pnpm -C rescript-mcp build && pnpm -C rescript-mcp test` → all pass, +1 test.

### Step 4: Parity verification (requires plan 045 landed)

If plan 045's status row is not DONE, run these anyway and record flakiness; the pass gate only applies post-045.

- `--case=get_table_schema-Customers.json` (read-only cases-dir) → `PASS` (the artifact's expected envelope: 11 fields + `recordCount: 5` + `primaryKey: null`)
- `--case=get_tables.json` → `PASS` (all 8 tables with real counts)
- Repeat each 3× — zero FAIL/ERROR.

**Verify**: outputs recorded; both cases PASS.

### Step 5: Record

- findings.md note + `plans/README.md` row → DONE (or DONE* with "verification pending plan 045" if 045 hasn't landed).
- Refresh `parity/findings.json` from the final run and commit it.

## Test plan

- New ComDdlTest real-COM test: Customers → recordCount 5, 11 fields (exact values, deterministic fixture).
- Updated pins: any prior `recordCount == 0` assertions on user tables.
- Differential: `get_table_schema-Customers.json` and `get_tables.json` PASS ×3 each.
- Regression: full suite green; ODBC parity `pnpm -C rescript-mcp parity:northwind` still 9/9 (ODBC path untouched).

## Done criteria

- [ ] `pnpm -C rescript-mcp build` exits 0
- [ ] `pnpm -C rescript-mcp test` → 0 failed, +1 new test
- [ ] `get_table_schema-Customers.json` parity PASS ×3 (post-045)
- [ ] `get_tables.json` parity PASS ×3 (post-045)
- [ ] `systemOnly` branch still returns `recordCount: 0` (no system-table counting)
- [ ] No files outside in-scope list modified
- [ ] findings.md + plans/README.md updated

## STOP conditions

- `_getTablesImpl` no longer matches the excerpt (structure changed since `016ebdb`).
- Opening a recordset inside the TableDefs iteration destabilizes the suite (new exit-134-style failures in COM tests beyond plan 045's known set) — report; do not ship a change that increases crash rate.
- The COUNT value for Customers is not 5 on the fixture — fixture drift; verify `db/northwind.accdb` has 8 tables / 5 customers before proceeding (STOP if not: someone mutated the fixture).
- The parity diff after this change is at a path OTHER than `recordCount` — record and report; other diffs belong to other plans.

## Maintenance notes

- This plan adds COM traffic per table (one recordset per user table per `getTables` call). If performance ever matters, cache per-connection with invalidation on mutations — explicitly deferred (python re-counts every call; parity first).
- Plan 045's release discipline applies to every handle the new helper touches: `_closeRecordset` handles the recordset; the Fields(0) intermediate must be released with `releaseSyncAwait` (or via a helper that does).
