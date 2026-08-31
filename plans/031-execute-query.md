# Plan 031: Implement DAO.OpenRecordset via executeQuery

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.

## Status

- **Priority**: P0 (blocks 032+; first real DAO capability)
- **Effort**: M
- **Risk**: LOW–MED (winax proxy semantics verified live in plan 030)
- **Depends on**: plans/030-winax-binding-fix.md (DONE, tip `48388f8`)
- **Category**: feature
- **Planned at**: commit `48388f8`, 2026-08-31

## Why

Plan 030's real-COM proof showed the connect chain works (`get(currentDb, "Name")` returned `"test_db.accdb"`). Now the first DAO capability lands: `executeQuery` (SELECT via `DAO.Database.OpenRecordset`). This unblocks parity-test schema reads (plan 032) and is the foundation for mutations (plan 032) and DDL (plan 033).

## Current state (verified at `48388f8`)

### Stub that must be replaced

`rescript-mcp/src/Adapters/ComDataAdapter.res` lines 173-179:

```rescript
Promise.resolve(Ok({
  success: false,
  rows: [],
  count: 0,
  columns: [],
  error: Some("COM executeQuery not yet fully implemented: winax binding incomplete"),
}))
```

The entire `_executeQueryImpl` body (lines 156-181) returns the above error envelope
unconditionally (even when connected). The `executeQuery` public function (lines 187-189)
delegates to it.

### Python reference (wincom.py:256-307 — `execute_query`)

```python
db = self._dispatcher.current_db
rs = db.OpenRecordset(sql)
if rs.EOF:
    rs.Close()
    return {"success": True, "rows": [], "count": 0, "columns": []}

# Read column names
columns = []
for i in range(rs.Fields.Count):
    columns.append(rs.Fields(i).Name)

# Read all rows
results = []
while not rs.EOF:
    row = {}
    for i, col in enumerate(columns):
        val = rs.Fields(i).Value
        if val is not None and hasattr(val, "strftime"):
            val = val.isoformat()
        row[col] = val
    results.append(row)
    rs.MoveNext()

rs.Close()
return {"success": True, "rows": results, "count": len(results), "columns": columns}
```

Key behaviors:
- `db.OpenRecordset(sql)` — DAO method returning a Recordset COM handle
- `rs.Fields.Count` — number of columns
- `rs.Fields(i).Name` — column header at index `i`
- `rs.Fields(i).Value` — cell value at index `i`
- `rs.EOF` — true when recordset is empty or exhausted
- `rs.MoveNext()` — advance cursor
- `rs.Close()` — release recordset
- Date values: convert via `isoformat()` if the value has `strftime`

### Live winax proxy semantics (plan 030 verification)

- `obj[prop]` reads a property (e.g. `db["Name"]`)
- `obj.method(args)` calls a method (e.g. `db.OpenRecordset(sql)`)
- `WINAX_BINDING.invokeAsObject(db, "OpenRecordset", [sqlArg])` — invokes method, returns COM handle wrapped as `{__p__: rs}` by the bridge
- `WINAX_BINDING.get(rs, "Fields")` — returns COM collection
- `WINAX_BINDING.getCount(fieldsCollection)` — returns field count
- `WINAX_BINDING.getItem(fieldsCollection, VInt(i))` — returns Field COM handle
- `WINAX_BINDING.get(fieldHandle, "Name")` / `WINAX_BINDING.get(fieldHandle, "Value")` — read field properties
- `WINAX_BINDING.release(rs)` — release recordset handle when done

## Commands

| Purpose | Command | Expected |
|---|---|---|
| Clean+build | `pnpm -C rescript-mcp clean:all && pnpm -C rescript-mcp build` | exit 0 |
| Test | `pnpm -C rescript-mcp test` | all pass, ≥ 725+N |
| Parity | `$env:ACCESS_TEST_ASSUME_ACE="1"; pnpm -C rescript-mcp parity:northwind` | 6/0/3 unchanged |
| Orphan check | `tasklist /FI "IMAGENAME eq MSACCESS.EXE"` | none after 3+ s settle |

## Scope

**In scope**:
- `plans/031-execute-query.md` (this file)
- `rescript-mcp/src/Adapters/ComDataAdapter.res` — replace `_executeQueryImpl` stub with real DAO implementation
- `rescript-mcp/test/ComExecuteQueryTest.res` (new file) — at least 3 tests: unit/fake, real-COM SELECT, error path
- `rescript-mcp/parity/findings.md` (new file) — record finding 028-F-001
- `plans/README.md` — row 031

**Out of scope**:
- Mutations (insert/update/delete) — plan 032
- Schema reads (tables/indexes/relations/queries/modules) — plan 032+
- DDL — plan 033
- `generateSql` — deferred
- Linked tables, compact/repair — deferred

## Git workflow

- Branch: `rescript/031-execute-query` from `48388f8`
- Commit 1: `feat(rescript-mcp): implement DAO.OpenRecordset via executeQuery`
- Commit 2: `test(rescript-mcp): add real-COM executeQuery integration tests`
- Commit 3: `docs(parity): record 028-F-001 D3 parity truth`
- Commit 4: `docs(plans): mark 031 done`
- Conventional commits, no AI attribution, no push, no PR.

## Steps

### Step 1: Verify clean state

```bash
git rev-parse --short HEAD        # expect: 48388f8
git status --short                # only untracked junk files
```

### Step 2: Branch

```bash
git checkout -b rescript/031-execute-query
```

### Step 3: Implement `_executeQueryImpl` in `ComDataAdapter.res`

Replace the stub `_executeQueryImpl` body (lines 156-181) with:

```
_doQuery: (session: ComSession.t, sql: string) => Promise.t<result<queryResult, Errors.t>>

The _doQuery function:
1. Guard: if not connected → return error envelope (same pattern as stub)
2. Get session.currentDb (the envelope-wrapped DAO Database — NOT session.handles.daoDb)
3. Call WINAX_BINDING.invokeAsObject(currentDb, "OpenRecordset", [sql]) → rs handle
4. Check rs.EOF via WINAX_BINDING.get(rs, "EOF"):
   - If EOF=true: WINAX_BINDING.release(rs); return {success:true, rows:[], count:0, columns:[]}
5. Read column names:
   - fields = WINAX_BINDING.get(rs, "Fields")
   - count = WINAX_BINDING.getCount(fields)
   - For i in 0..count-1: fieldHandle = WINAX_BINDING.getItem(fields, VInt(i))
                            colName = WINAX_BINDING.get(fieldHandle, "Name") → JSON.String name
   - Release each fieldHandle after use
6. Read all rows (forward-only iteration):
   - While not EOF:
     - row = {}
     - For each column i: get fieldHandle, get Value, convert, store in row
       - Date detection: if JSON.String matches ISO date pattern, convert to ISO string (matching Python isoformat())
     - Push row to results array
     - WINAX_BINDING.invoke(rs, "MoveNext", []) to advance
     - Check EOF again
7. WINAX_BINDING.release(rs) — always, in a finally pattern
8. Return {success:true, rows:results, count:len(results), columns:columns}

Value conversion (matching Python _formatDaoValue):
- Date objects → ISO string (via Date.toISOString)
- null/empty → JSON.Null
- numbers → JSON.Number
- strings → JSON.String
- booleans → JSON.Boolean
- arrays → JSON.Array
- objects → JSON.Object
- Other → JSON.Null (safe fallback)

Handle dispatch errors via WINAX_BINDING.mapDispatchError.
```

**Critical reminders**:
- Use `session.currentDb` — the envelope-wrapped DAO Database handle
- Use `invokeAsObject` for OpenRecordset (returns COM handle — bridge auto-wraps in `{__p__: rs}`)
- Use `invoke` for `MoveNext` (no return value to capture)
- Use `get` for property reads (`EOF`, `Fields`, `Name`, `Value`)
- Use `getCount` + `getItem` for iterating Fields collection
- Use `fromVariant` for converting field `Value` (Variant → JSON.t)
- Release recordset handle with `release(rs)` when done (forward-only: release after full iteration)

### Step 4: Write `ComExecuteQueryTest.res`

Create `rescript-mcp/test/ComExecuteQueryTest.res` with:

**Test A (unit/fake)**: `FakeWinaxBinding` returns a mock recordset with 2 columns, 3 rows. Verify:
- `executeQuery` returns `{success:true, count:3, columns:["id","name"], rows:[...]}`
- Each row has correct column values

**Test B (real-COM)**: Probe-gated. SELECT id, name FROM Customers against test_db.accdb.
Verify: success=true, count > 0, columns include "id" and "name", rows populated.
Pattern: same probe gate as `ComIntegrationTest.res:19-50`.

**Test C (real-COM, error)**: Probe-gated. Empty SQL string.
Verify: returns error envelope (success:false, error:Some(...)) — does not crash.

**Test D (real-COM, empty result)**: Probe-gated. SELECT * FROM Customers WHERE 1=0.
Verify: success:true, rows:[], count:0.

### Step 5: Build and test

```bash
pnpm -C rescript-mcp clean:all
pnpm -C rescript-mcp build
pnpm -C rescript-mcp test
```

Expected: all pass, test count ≥ 725+N.

### Step 6: Parity run

```bash
$env:ACCESS_TEST_ASSUME_ACE="1"; pnpm -C rescript-mcp parity:northwind
```

Verify: 6 matched / 0 mismatched / 3 errored (count unchanged; message may update).

### Step 7: Record 028-F-001 finding

Create `rescript-mcp/parity/findings.md`:

```markdown
## 028-F-001: D3 Parity Truth — Stub Attribution Wrong

**Finding**: The 3 errored parity cases (`get_table_schema-Customers.json`,
`get_table_schema-Orders.json`, `get_table_schema-Products.json`) were attributed
in plan 027 to "no Access" or missing COM capability.

**Real root cause**: The ReScript `executeQuery` function (and adjacent schema
methods) were stubs returning "winax binding incomplete" error envelopes. These
were not runtime failures due to missing Access — they were stub implementations
that never attempted real COM calls.

**Resolution**: Plan 031 implements `executeQuery` via `DAO.Database.OpenRecordset`.
The 3 errored cases still error (plan 032 implements schema reads), but the
error messages are now meaningful COM errors rather than "binding incomplete".

**Status**: executeQuery resolved (031); schema reads remain plan 032+.
```

### Step 8: Closeout

Update `plans/README.md` row 031 → DONE (final SHA, test count, note about 028-F-001).

Commit `docs(plans): mark 031 done`.

## Done criteria

- [ ] `grep -n "winax binding incomplete" rescript-mcp/src/Adapters/ComDataAdapter.res` → no matches
- [ ] `plans/031-execute-query.md` exists and is self-contained
- [ ] `pnpm -C rescript-mcp clean:all && pnpm -C rescript-mcp build` → exit 0
- [ ] `pnpm -C rescript-mcp test` → all pass, test count ≥ 725+N
- [ ] At least 3 new tests (≥1 real-COM probe-gated)
- [ ] Parity: 6 matched / 0 mismatched / 3 errored (count unchanged; messages may update)
- [ ] No MSACCESS.EXE orphan 3+ s after suite
- [ ] `028-F-001` finding recorded in `rescript-mcp/parity/findings.md`
- [ ] `plans/README.md` row 031 updated; conventional commits

## STOP conditions

- `DAO.OpenRecordset` signature differs from assumed — verify live
- `__p__` envelope unwrapping fails for Recordset COM handle — debug live
- Any existing test regresses
- Parity baseline changes count (6/0/3)
- Suite hangs > 60 s
- MSACCESS.EXE orphan persists > 10 s after suite
