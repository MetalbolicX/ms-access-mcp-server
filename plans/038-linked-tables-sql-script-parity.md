# Plan 038 — Port the 6 remaining ISchemaAdapter methods (linked tables + SQL script) with parity

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> `git status` → zero uncommitted `src/`/`test/` changes (dirty tree = STOP).
> `git diff --stat 6d6ab63..HEAD -- rescript-mcp/src/Adapters/Interfaces.res rescript-mcp/src/Adapters/Instances.res rescript-mcp/src/Adapters/ComDataAdapter.res rescript-mcp/src/Adapters/OdbcAdapter.res rescript-mcp/src/Services/Facade.res rescript-mcp/src/Services/Composition.res rescript-mcp/parity/runRescript.ts rescript-mcp/scripts/parity_driver.py rescript-mcp/parity/cases.schema.json rescript-mcp/test/Fakes.res`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED (winax object marshalling + envelope-shape parity; all patterns have in-repo precedents cited below)
- **Depends on**: plans/036-parity-oracle-com-fix.md (DONE, T6 deferred to here)
- **Category**: tech-debt (parity completion) · **Methodology**: STRICT TDD
- **Planned at**: commit `6d6ab63`, 2026-09-02

## Why this matters

The ReScript `SCHEMA_ADAPTER` surface is 22 methods; the Python
`ISchemaAdapter` contract has 28. The 6 missing methods (5 linked-table ops +
`execute_sql_script`) mean the ReScript server silently lacks a whole
capability class the Python server exposes, and parity cannot even measure
the gap because neither driver dispatches these operations. This plan ports
all 6 with strict-TDD parity against the live Python oracle, wires both
parity drivers, and adds 12 case files (6 COM success-path, 6 ODBC
error-path) so the differential harness permanently guards the surface.

## Environment quirks (binding for executors)

Same as plan 036 §Environment quirks 1 (which amends plan 035):

1. pnpm via `cmd.exe /c` wrapper: `cmd.exe /c "pnpm -C rescript-mcp build"`.
2. Python is ALWAYS `.venv\Scripts\python.exe` — never `uv`, never `python`.
3. Kill `MSACCESS.EXE` before and after any COM-touching run:
   `Get-Process MSACCESS -ErrorAction SilentlyContinue | Stop-Process -Force`.
4. `db/northwind.accdb` AND `db/postgres.accdb` are pristine fixtures —
   never mutated, never committed with changes (`git status -- db/` clean).
5. Clean target is `clean:all`, never `clean` alone (AGENTS.md).
6. Fresh-build gate: any "suite is green" claim requires
   `pnpm -C rescript-mcp clean:all` + full rebuild first (plans/README.md
   authoring standard #7).

## Current state (verified at `6d6ab63`)

### Python oracle — the behavior contract

- `src/ms_access_mcp/adapters/interfaces.py:70-77` — the 6 signatures:
  `get_linked_tables() -> dict`, `create_linked_table(name, source_table,
  connect_string) -> dict`, `refresh_linked_table(name, connect_string=None)
  -> dict`, `recreate_linked_table(name, source_table, connect_string,
  attributes=None) -> dict`, `unlink_table(name) -> dict`,
  `execute_sql_script(script_path) -> dict`.
- Linked tables — canonical impls in `src/ms_access_mcp/adapters/dao.py`:
  - `get_linked_tables` `dao.py:1185-1235`: iterate `db.TableDefs`, keep
    entries with `Attributes & 0x80000000`, classify `type` from the
    connect-string prefix (`ODBC`/`Access`/`Excel`, unknown → `ODBC`), emit
    `{name, source_table, connect_string, type, attributes}` per link.
  - `create_linked_table` `dao.py:1237-1273`: `db.CreateTableDef(name)` →
    set `SourceTableName`, `Connect`, `Attributes = 0x80000000` →
    `TableDefs.Append(tdef)` → `tdef.Connect = _strip_password(cs)`.
  - `refresh_linked_table` `dao.py:1275-1315`: `TableDefs(name)` → if
    `connect_string` supplied, set `Connect` → `RefreshLink()` →
    `Connect = _strip_password(tdef.Connect)` (reads post-refresh value).
  - `recreate_linked_table` `dao.py:1317-1386`: capture old `Attributes`
    (fallback `0x80000000` if unreadable) → `TableDefs.Delete(name)` →
    create+append (Attributes `0x80000000`) → restore captured Attributes →
    strip password.
  - `unlink_table` `dao.py:1388-1411`: `TableDefs.Delete(name)`.
  - `WinComAdapter` delegates all 5 to the composed DaoAdapter
    (`wincom.py:845-869`) — parity is by construction.
- `execute_sql_script` — `wincom.py:1046-1151`: file-exists check →
  `"File not found: {path}"` envelope; not-connected → `"Not connected"`
  envelope (both with `statements_executed: 0` and all-null fields,
  `wincom.py:1062-1082`); reads file utf-8; parses via
  `_parse_script_lines` (`wincom.py:1153-1198`); empty statements → success
  with `statements_executed: 0` (`:1102-1110`); executes each statement via
  **ADO** `self._dispatcher.ado_conn.Execute(text)` (`:1112-1116`); on
  failure returns `{success: False, statements_executed: <executed>,
  error, failing_statement, failing_line, access_error_code,
  access_error_message}` (`:1118-1128`); success returns all 7 keys with
  nulls (`:1130-1137`).
- `_strip_sql_comments` `wincom.py:1024-1036` — three regexes:
  `(?m)^\s*--.*$` → "", `/\*.*?\*/` (DOTALL) → "", `\n\s*\n` → `\n`.
- `_strip_password` → `ConnectPolicy.sanitize`
  (`orchestrators/connect_policy.py:147-162`): plain (case-SENSITIVE) regex
  `PWD=[^;]*;?` removed. Nothing else.
- ODBC error contract (exact strings, load-bearing for error parity):
  - `get/create/refresh/recreate/unlink_linked_table` raise via
    `com_only_mixin.py:414-438`:
    `"<method_snake> requires COM automation (WinComAdapter)"`.
  - `execute_sql_script` — `OdbcAdapter`'s OWN override wins
    (`odbc.py:483-485`): `"execute_sql_script requires COM (WinComAdapter)"`
    (no word "automation"). Do not "fix" this inconsistency — mirror it.

### Link source fixture (probe-verified 2026-09-02)

`db/postgres.accdb` is a **self-contained local Access database** — DAO
probe shows `categories`, `customers`, `order_items`, `orders`, `products`
all `linked=False` with empty `Connect` strings. Despite the name, it needs
NO PostgreSQL server, NO docker, NO ODBC DSN. Linked-table parity works
file-to-file: connect string `;DATABASE=<abs path to postgres.accdb>`.
Re-verify before starting:

```
& .venv\Scripts\python.exe -c "import win32com.client; db=win32com.client.Dispatch('DAO.DBEngine.120').OpenDatabase(r'db\postgres.accdb',False,True); print([ (t.Name, bool(t.Attributes & 0x80000000)) for t in db.TableDefs if not t.Name.startswith('MSys')]); db.Close()"
```

Expected: all five tables with `linked=False`.

### ReScript side — every seam this plan touches

- `rescript-mcp/src/Adapters/Interfaces.res:130-156` (+`.resi:134-159`) —
  `SCHEMA_ADAPTER` module type, 22 methods, none of the 6 present.
- `rescript-mcp/src/Adapters/Instances.res:45-68` —
  `schemaAdapterInstance` record-of-closures, 22 fields (FROZEN SEAM
  CONTRACT comment — extend it; field order stays append-only).
- `rescript-mcp/src/Adapters/OdbcAdapter.res` — `createQuery`
  `:1453-1475` is the stub-style precedent; `generateSql` `:960` shows the
  com-only envelope style.
- `rescript-mcp/src/Adapters/ComDataAdapter.res` (module `DaoAdapter`):
  - not-connected/session/db guard triple — `createQuery` `:1267-1299`.
  - collection iteration (get → getCount → getItem loop → %raw reads) —
    Relations `:862-935`; `%raw` property reads via `__p__` — `:893-897`.
  - named collection item via `invokeAsObject(db, "QueryDefs", [VStr(name)])`
    — `:1313` (reuse for `TableDefs(name)`).
  - collection Delete — `invoke(qdefsHandle, "Delete", [VStr(name)])`
    `:1354-1370`.
  - **object-as-invoke-argument precedent (the crux)** —
    `createRelationship` appends a COM object to a collection:
    `:2410-2411`
    `let relAsVariant: ComInterfaces.variant = %raw("(r) => r")(Obj.magic(rel))`
    then `invoke(relsHandle, "Append", [relAsVariant])`. Copy this exact
    pattern for `TableDefs.Append(tdef)`.
  - `asSchemaInstance` — `:2571+` (needs 6 new delegating fields).
  - `_exnMessage` hardened extractor — `:52-68` (use for all error paths).
- `rescript-mcp/src/Adapters/ComInterfaces.res:42-46` —
  `sessionHandles.adoConn: option<comObject>`; created best-effort at
  connect (`ComSession.res:200-208`), released LIFO at disconnect
  (`ComSession.res:255-262`).
- `rescript-mcp/src/Services/Composition.res:21-126` — ODBC
  `asSchemaInstance` (needs 6 stub-delegating fields).
- `rescript-mcp/src/Services/Facade.res` — `_shapeDdlResult` `:854-872`;
  wrapper precedents: `setQuerySql` `:1108-1126` (readonly guard +
  adapter-for-name), `generateSql` `:1173-1185` (NO readonly guard);
  `createQuery` `:1152-1170` + its tests.
- `rescript-mcp/parity/runRescript.ts:215-247` — DDL dispatch cases;
  `REPLACE_AT_RUNTIME` handling precedent `:202-213`.
- `rescript-mcp/parity/types/facade.d.ts:65-68` — typed facade surface used
  by the TS runner (add 6 signatures after `generateSql`).
- `rescript-mcp/scripts/parity_driver.py:426-487` — `_run_op` dispatch;
  shape-helper precedents `:394-419`. mypy strict — keep annotations.
- `rescript-mcp/parity/run.ts:119-132` — `pinnedEnv` (add
  `PARITY_SOURCE_DB`); per-child env `:213-225`.
- `rescript-mcp/parity/cases.schema.json:13-41` — operation enum (27
  entries; add 6).
- `rescript-mcp/test/Fakes.res:297-513` — `FakeSchemaAdapter` (22 methods)
  + `asInstance`; call-logging precedent `createQuery` `:404-411`.
- `rescript-mcp/test/InstancesTest.res:120-148` — "all 22 schema methods"
  callable test (extend to 28).
- `rescript-mcp/test/OdbcAdapterDdlTest.res` — ODBC stub-test patterns.
- `rescript-mcp/test/ComDdlTest.res:1153-1193` — COM not-connected tests;
  `:1196-1250` — real-COM probe-gated tests (Access-unavailable skip).
- `rescript-mcp/test/FacadeTest.res:2150-2237` — plan 036 T2 DDL routing
  tests (the model for the 6 new Facade tests). NOTE: append new tests at
  file end only — two identical "Structural: no Bindings" anchors earlier in
  the file have caused duplicate-insertion diffs before.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Build | `cmd.exe /c "pnpm -C rescript-mcp clean:all"` then `cmd.exe /c "pnpm -C rescript-mcp build"` | exit 0, "Compiled" |
| Suite | `cmd.exe /c "pnpm -C rescript-mcp test"` | 0 NEW failures beyond the 9 pre-existing COM-env ones; total ≥ 774 |
| Parity ODBC ddl | `cmd.exe /c "pnpm -C rescript-mcp parity:northwind:ddl"` | 13 matched + 2 skipped |
| Parity COM ddl | `cmd.exe /c "pnpm -C rescript-mcp parity:northwind:com:ddl"` | 14 matched + 1 skipped |
| Parity baseline | `cmd.exe /c "pnpm -C rescript-mcp parity:northwind"` | 9/9 matched |
| Python probe | `& .venv\Scripts\python.exe <script>` | per-step expected output |

Env for parity runs (PowerShell):
`$env:ACCESS_TEST_ASSUME_ACE='1'; $env:ACCESS_TEST_DB="$PWD\db\northwind.accdb"; $env:ACCESS_MCP_ALLOWED_DIRS="$PWD\db;$env:TEMP"; $env:ACCESS_MCP_READONLY='false'`

## Scope

**In scope** (the only files you should modify/create):
- `rescript-mcp/src/Adapters/Interfaces.res` + `.resi`
- `rescript-mcp/src/Adapters/Instances.res`
- `rescript-mcp/src/Adapters/OdbcAdapter.res`
- `rescript-mcp/src/Adapters/ComDataAdapter.res`
- `rescript-mcp/src/Services/Composition.res`
- `rescript-mcp/src/Services/Facade.res`
- `rescript-mcp/parity/runRescript.ts` (+regenerated `.mjs` build output if the build produces it)
- `rescript-mcp/parity/types/facade.d.ts`
- `rescript-mcp/parity/run.ts`
- `rescript-mcp/scripts/parity_driver.py`
- `rescript-mcp/parity/cases.schema.json`
- 12 new case files under `rescript-mcp/parity/cases/northwind/{com/ddl,ddl}/`
- `rescript-mcp/test/{Fakes.res,InstancesTest.res,OdbcAdapterDdlTest.res,ComDdlTest.res,FacadeTest.res}`
- `rescript-mcp/parity/findings.md`, `plans/README.md` (docs at the end)

**Out of scope** (do NOT touch):
- MCP tool exposure (`src/Mcp/Tools.res`, `Server.res`) — the 6 ops are
  parity-surface only; MCP tools are a separate future change.
- A failing-script `execute_sql_script` parity case — ADO-vs-driver error
  codes diverge; envelope FIELDS ship now, the error-path CASE is deferred
  (see Maintenance notes).
- Plans 037a–037e (IUiAdapter port) — number reserved.
- 033-F-001 winax teardown fix; `com/ddl/generate_sql.json` stays skipped.
- `db/postgres.accdb`, `db/northwind.accdb` (read-only fixtures).
- Python source under `src/ms_access_mcp/` — the oracle is the contract;
  ANY divergence you are tempted to "fix" in Python is a findings entry,
  not an edit.

## Git workflow

- Branch: `rescript/038-linked-tables-sql-script` from `6d6ab63`.
- Conventional commits, e.g. `feat(parity): port linked-table ops to COM adapter`,
  `test(parity): add 12 linked/script parity cases`. One commit per plan step
  is fine; keep the suite green at every commit.
- Do NOT push or open a PR unless instructed.

## Design (verbatim — binding for executors; deviation is a STOP)

### D1. New types — `Interfaces.res` + `.resi` (identical blocks in both)

```rescript
type linkedTableInfo = {
  name: string,
  sourceTable: string,
  connectString: string,
  type_: string,
  attributes: int,
}

type linkedTablesResult = {
  success: bool,
  error: option<string>,
  linkedTables: array<linkedTableInfo>,
}

type sqlScriptResult = {
  success: bool,
  error: option<string>,
  statementsExecuted: int,
  failingStatement: option<string>,
  failingLine: option<int>,
  accessErrorCode: option<int>,
  accessErrorMessage: option<string>,
}
```

### D2. `SCHEMA_ADAPTER` additions (both `.res` and `.resi`)

```rescript
let getLinkedTables: t => Promise.t<result<linkedTablesResult, Errors.t>>
let createLinkedTable: (t, string, string, string) => Promise.t<result<ddlResult, Errors.t>>
let refreshLinkedTable: (t, string, ~connectString: option<string>=?) => Promise.t<result<ddlResult, Errors.t>>
let recreateLinkedTable: (t, string, string, string, ~attributes: option<int>=?) => Promise.t<result<ddlResult, Errors.t>>
let unlinkTable: (t, string) => Promise.t<result<ddlResult, Errors.t>>
let executeSqlScript: (t, string) => Promise.t<result<sqlScriptResult, Errors.t>>
```

### D3. `Instances.res` `schemaAdapterInstance` — append 6 fields

```rescript
getLinkedTables: unit => Promise.t<result<linkedTablesResult, Errors.t>>,
createLinkedTable: (string, string, string) => Promise.t<result<ddlResult, Errors.t>>,
refreshLinkedTable: (string, ~connectString: option<string>=?) => Promise.t<result<ddlResult, Errors.t>>,
recreateLinkedTable: (string, string, string, ~attributes: option<int>=?) => Promise.t<result<ddlResult, Errors.t>>,
unlinkTable: string => Promise.t<result<ddlResult, Errors.t>>,
executeSqlScript: string => Promise.t<result<sqlScriptResult, Errors.t>>,
```

(Type aliases `linkedTablesResult`/`sqlScriptResult` alongside the existing
aliases at `Instances.res:14-23`.)

### D4. ODBC stubs — `OdbcAdapter.res` (exact error strings; mirror, don't fix)

- `getLinkedTables` → `Ok({success: false, error: Some("get_linked_tables requires COM automation (WinComAdapter)"), linkedTables: []})`
- `createLinkedTable` → `Ok({success: false, error: Some("create_linked_table requires COM automation (WinComAdapter)")} : ddlResult)`
- `refreshLinkedTable` / `recreateLinkedTable` / `unlinkTable` → same shape
  with their own method names in the message.
- `executeSqlScript` → `Ok({success: false, error: Some("execute_sql_script requires COM (WinComAdapter)"), statementsExecuted: 0, failingStatement: None, failingLine: None, accessErrorCode: None, accessErrorMessage: None})`
  — note: NO "automation" (matches `odbc.py:485`, which overrides the mixin).

### D5. COM helpers — module-level in `ComDataAdapter.res` (above `DaoAdapter`)

```rescript
// Exact port of ConnectPolicy.sanitize (connect_policy.py:162) — case-sensitive.
let _stripPassword = (cs: string): string =>
  %raw("cs => cs.replace(/PWD=[^;]*;?/g, '')")(cs)

let _classifyConnectType = (cs: string): string =>
  if cs->String.startsWith("ODBC") { "ODBC" }
  else if cs->String.startsWith("Access") { "Access" }
  else if cs->String.startsWith("Excel") { "Excel" }
  else { "ODBC" }
```

Parser — exported for unit testing (port of `wincom.py:1153-1198` +
`:1024-1036`):

```rescript
// Strip SQL comments exactly as Python _strip_sql_comments (wincom.py:1024-1036).
let _stripSqlComments = (sql: string): string =>
  %raw(`sql => sql.replace(/^\s*--.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "").replace(/\n\s*\n/g, "\n")`)(sql)

// Parse raw SQL into (text, 1-based-line) pairs — port of _parse_script_lines.
let parseScriptLines = (rawSql: string): array<(string, int)> => { ... }
```

Algorithm (must match Python statement-for-statement): iterate `remaining`
splitting on the next `";"`; skip chunks that are empty after strip OR empty
after comment-strip; compute `firstContent = leading-whitespace length of
rawChunk`; `stmtPos = pos + firstContent`; `line = count of "\n" in
rawSql[:stmtPos] + 1`; advance `pos += len(rawChunk) + (1 if semicolon found
else 0)` in ALL branches (skip branches included). Implement in ReScript
with `Js.String.splitAtMost`/index arithmetic or a `%raw` port — either is
acceptable; the TESTS pin the behavior, not the implementation.

### D6. COM method bodies — patterns (follow cited precedents exactly)

All 6 start with the guard triple from `createQuery :1267-1277`
(not-connected / no-session / no-db → `{success: false, error: Some(...)}`,
inside `Ok`).

- `getLinkedTables`: `get(db, "TableDefs")` → envelope → `getCount` →
  recursive `getItem` loop (Relations pattern `:862-935`); per tdef read via
  `%raw("h => h && h.__p__ ? ... : ...")`: `Name`, `Connect` (`|| ""`),
  `SourceTableName` (`|| ""`), `Attributes` (`Number(...) || 0`); keep when
  `%raw` bitwise `(attrs & 0x80000000) !== 0`; build `linkedTableInfo` with
  `_classifyConnectType(connect)`; release each tdef; release the
  collection after the loop; resolve `Ok({success: true, error: None,
  linkedTables: results})`.
- `createLinkedTable(name, sourceTable, connectString)`:
  `invokeAsObject(db, "CreateTableDef", [VStr(name)])` → tdef;
  `set(tdef, "SourceTableName", VStr(sourceTable))`;
  `set(tdef, "Connect", VStr(connectString))`;
  `set(tdef, "Attributes", VInt(2147483648))` — `0x80000000`; if winax
  rejects with an overflow error, use `VInt(-2147483648)` (same bits, DAO
  Long is signed; both must be tried before declaring failure);
  `get(db, "TableDefs")` → tableDefs; then the `:2410-2411` object-arg
  pattern: `let tdefAsVariant: ComInterfaces.variant = %raw("(t) => t")(Obj.magic(tdef))`
  and `invoke(tableDefs, "Append", [tdefAsVariant])`; then
  `set(tdef, "Connect", VStr(_stripPassword(connectString)))`; release
  tdef + tableDefs; `Ok({success: true, error: None})`. Any step `Error` →
  release what was acquired and return
  `Ok({success: false, error: Some(Errors._message(e) / _exnMessage(e))})`.
- `refreshLinkedTable(name, ~connectString=?)`:
  `invokeAsObject(db, "TableDefs", [VStr(name)])` → tdef (precedent
  `:1313`); if `Some(cs)` → `set(tdef, "Connect", VStr(cs))`;
  `invoke(tdef, "RefreshLink", [])`; read back
  `%raw("h => h && h.__p__ && h.__p__.Connect != null ? h.__p__.Connect : ''")`;
  `set(tdef, "Connect", VStr(_stripPassword(current)))`; release; success.
- `recreateLinkedTable(name, sourceTable, connectString, ~attributes=?)`:
  resolve `attrs` = explicit arg, else try
  `invokeAsObject(db, "TableDefs", [VStr(name)])` → `%raw` `Attributes`
  (`Number(...) || 0`), else `2147483648` on error; `get(db, "TableDefs")` →
  `invoke(tableDefs, "Delete", [VStr(name)])` (precedent `:1364`); then the
  createLinkedTable sequence; then `set(tdef, "Attributes", VInt(attrs))`;
  then `set(tdef, "Connect", VStr(_stripPassword(connectString)))`; release
  everything; success.
- `unlinkTable(name)`: `get(db, "TableDefs")` → `invoke(handle, "Delete",
  [VStr(name)])` → release → success (mirror `deleteQuery :1354-1370`).
- `executeSqlScript(scriptPath)`:
  1. `!NodeJs.Fs.existsSync(scriptPath)` → full 7-key envelope,
     `error = Some("File not found: " ++ scriptPath)`, `statementsExecuted: 0`,
     rest `None`.
  2. not connected → same shape, `error = Some("Not connected")`.
  3. `NodeJs.Fs.readFileSync(scriptPath, "utf8")` → `parseScriptLines`.
  4. empty → success envelope, `statementsExecuted: 0`, all-null fields.
  5. per statement: `switch session.handles.adoConn` —
     `Some(ado)` → `invokeAsObject(ado, "Execute", [VStr(text)])` → the
     result is a Recordset envelope: **`release` it immediately** (Python
     discards it; a leaked recordset holds DB locks);
     `None` → return full envelope
     `error = Some("No ADO connection")`, `statementsExecuted: 0` (do NOT
     silently fall back to DAO `db.Execute` — error-code parity risk).
  6. statement failure → full envelope with `statementsExecuted = <count so
     far>`, `failingStatement = Some(text)`, `failingLine = Some(line)`,
     `error = Some(_exnMessage(e))`, `accessErrorCode/accessErrorMessage =
     None` (winax does not expose scode through the extractor; the
     failing-script parity case is deferred — see Out of scope).
  7. all executed → success envelope, `statementsExecuted = n`, nulls.

### D7. Facade wrappers + shapers — `Facade.res`

Shapers (new; do NOT reuse `_shapeDdlResult` for these — key sets differ):

```rescript
// Python success envelope has NO error key; failure envelope (driver catch
// or adapter error) has NO linked_tables key. Emit per-outcome keys exactly.
let _shapeLinkedTablesResult = (r: result<Interfaces.linkedTablesResult, Errors.t>): dict<JSON.t> => ...
// ALWAYS all 7 keys — Python envelopes (wincom.py:1103-1137) always carry them.
let _shapeSqlScriptResult = (r: result<Interfaces.sqlScriptResult, Errors.t>): dict<JSON.t> => ...
```

JSON keys (snake_case, matching Python): `linked_tables`, `name`,
`source_table`, `connect_string`, `type`, `attributes` (JSON.Number),
`statements_executed`, `failing_statement`, `failing_line`,
`access_error_code`, `access_error_message` (None → JSON.Null).

Wrappers:
- `getLinkedTables(facade, ~name=?)` — NO readonly guard (generateSql
  precedent `:1173-1185`); `schemaAdapterForName` → adapter.getLinkedTables()
  → `_shapeLinkedTablesResult`.
- `createLinkedTable(~name_=`lnk`, ~sourceTable, ~connectString, ~name=?)`,
  `refreshLinkedTable(~tableName, ~connectString=?, ~name=?)`,
  `recreateLinkedTable(~name_, ~sourceTable, ~connectString, ~attributes=?, ~name=?)`,
  `unlinkTable(~tableName, ~name=?)`, `executeSqlScript(~scriptPath, ~name=?)`
  — each: `assertNotReadonly(facade, ~opName="<snake_op>")` then
  `schemaAdapterForName` then adapter call then shape
  (linked mutators → `_shapeDdlResult`; script → `_shapeSqlScriptResult`).
  opNames: `create_linked_table`, `refresh_linked_table`,
  `recreate_linked_table`, `unlink_table`, `execute_sql_script`.
  (Exact labeled-arg names are yours to choose for compile-ergonomics; the
  opName strings and guard order are binding.)

### D8. `facade.d.ts` — add after `generateSql` (line 68)

```typescript
getLinkedTables: (facade: Facade, opts?: { name?: string }) => Promise<Record<string, JsonT>>;
createLinkedTable: (facade: Facade, tableName: string, sourceTable: string, connectString: string, name?: string) => Promise<Record<string, JsonT>>;
refreshLinkedTable: (facade: Facade, tableName: string, connectString: string | undefined, name?: string) => Promise<Record<string, JsonT>>;
recreateLinkedTable: (facade: Facade, tableName: string, sourceTable: string, connectString: string, attributes: number | undefined, name?: string) => Promise<Record<string, JsonT>>;
unlinkTable: (facade: Facade, tableName: string, name?: string) => Promise<Record<string, JsonT>>;
executeSqlScript: (facade: Facade, scriptPath: string, name?: string) => Promise<Record<string, JsonT>>;
```

### D9. Harness placeholders (both drivers, IDENTICAL semantics)

- `PARITY_SOURCE_DB` — new env var. `run.ts` sets it in `pinnedEnv`:
  `PARITY_SOURCE_DB: join(REPO_ROOT, "db", "postgres.accdb")` and fails
  fast (clear message, exit 1) if that file is missing. Both children read
  it; in `runRescript.ts` and `parity_driver.py`, for the three ops taking
  `connect_string`, replace every `"REPLACE_SOURCE_DB"` substring in the
  arg with `process.env.PARITY_SOURCE_DB` / `os.environ["PARITY_SOURCE_DB"]`
  BEFORE dispatch. (Connect strings are not PathGuard-validated — no
  allowed-dirs change needed.)
- `script_path: "REPLACE_AT_RUNTIME"` — each driver writes the SAME fixed
  script content to its own temp file (`PARITY_EXPORT_DIR` or os tmpdir,
  name `parity_script_<pid>.sql`) and passes the absolute path:

```sql
-- parity linked script header comment
CREATE TABLE [ParityScriptTest] ([ID] INTEGER, [Label] TEXT);
/* mid-file block comment */
INSERT INTO [ParityScriptTest] ([ID], [Label]) VALUES (1, 'alpha');
INSERT INTO [ParityScriptTest] ([ID], [Label]) VALUES (2, 'beta');
```

  (LF newlines; trailing newline after last line. Expect
  `statements_executed == 3` — the parser must skip both comment forms.)

### D10. `parity_driver.py` — 6 shape helpers + dispatch + NotImplementedError catch

- `_shape_get_linked_tables(adapter)`: `try: return adapter.get_linked_tables()`
  `except NotImplementedError as e: return {"success": False, "error": str(e)}`
  (success dict passes through — it is already envelope-shaped).
- `_shape_create/refresh/recreate/unlink`: wrap the call, `except
  NotImplementedError as e: return {"success": False, "error": str(e)}`,
  otherwise `_shape_ddl_result(result)`.
- `_shape_execute_sql_script`: `except NotImplementedError as e:` return
  the FULL 7-key envelope `{"success": False, "statements_executed": 0,
  "error": str(e), "failing_statement": None, "failing_line": None,
  "access_error_code": None, "access_error_message": None}` — matching the
  ReScript stub shape exactly; otherwise pass the adapter dict through.
- Six branches in `_run_op` (mirror the `set_query_sql` block `:476-477`),
  with the D9 placeholder replacements applied to `args` first.
- mypy strict: annotate helpers `-> dict[str, Any]`.

### D11. `cases.schema.json` — enum += (insert after `"generate_sql"`)

`"get_linked_tables"`, `"create_linked_table"`, `"refresh_linked_table"`,
`"recreate_linked_table"`, `"unlink_table"`, `"execute_sql_script"`.
Update the enum `description` to mention plan 038.

### D12. Case files (12)

COM variant — `cases/northwind/com/ddl/` (all `variant: "com"`,
`mutating: true`, `volatileFields: []`, `connection_name: "northwind"`;
source link args: `name: "lnk_categories"`, `source_table: "categories"`,
`connect_string: ";DATABASE=REPLACE_SOURCE_DB"`):

| File | setup | main op args |
|---|---|---|
| `create_linked_table.json` | — | the link args above |
| `get_linked_tables.json` | 1 step: `create_linked_table` | `{}` |
| `refresh_linked_table.json` | 1 step: `create_linked_table` | name + same connect_string |
| `recreate_linked_table.json` | 1 step: `create_linked_table` (categories) | same name, `source_table: "customers"`, same connect_string |
| `unlink_table.json` | 1 step: `create_linked_table` | `name` only |
| `execute_sql_script.json` | — | `script_path: "REPLACE_AT_RUNTIME"` |

ODBC variant — `cases/northwind/ddl/` (all `variant: "odbc"`,
`mutating: false`, no setup, `connection_name: "northwind"`):
`get_linked_tables.json`, `create_linked_table.json`,
`refresh_linked_table.json`, `recreate_linked_table.json`,
`unlink_table.json` (ODBC cases never see `REPLACE_SOURCE_DB` — stubs error
before any path use; give them the same connect_string anyway for shape
completeness), and `execute_sql_script.json`
(`script_path: "REPLACE_AT_RUNTIME"` — the stub errors before file access).

## Steps

### Step 1: Type seams + ODBC stubs + fakes (scaffold + first TDD slice)

1. Write the ODBC stub tests FIRST in `OdbcAdapterDdlTest.res` (6 tests:
   call each new `OdbcAdapter` fn on a non-connected adapter; assert
   `Ok` + exact error string from D4, and for get/script the full record
   shape). They will not compile — that is RED.
2. Add D1 types to `Interfaces.res` + `.resi`; D2 signatures; D3 fields;
   D4 stubs in `OdbcAdapter.res`; wire the 6 fields in
   `Composition.asSchemaInstance` (delegate to the stubs);
   `Fakes.FakeSchemaAdapter`: 6 methods (log `SchemaCall`, return
   success-shaped records — `getLinkedTables` → `linkedTables: []`) + 6
   `asInstance` fields; extend `InstancesTest.res:120-148` to all 28.
3. `ComDataAdapter.DaoAdapter`: add the 6 methods as not-connected-envelope
   stubs (guard triple only) + 6 `asSchemaInstance` fields, so the whole
   program compiles.

**Verify**: clean:all + build → exit 0; test → 0 new failures (InstancesTest
now 28/28; the 6 new ODBC tests green).

### Step 2: Facade wrappers (TDD via fakes)

1. Append 6 Facade tests to the END of `FacadeTest.res` (model: plan 036
   T2 block `:2153-2237`): routing + success envelope for
   `getLinkedTables`/`createLinkedTable`/`executeSqlScript`; readonly
   rejection (adapter NOT called) for `createLinkedTable` and
   `executeSqlScript`. RED (no such Facade functions).
2. Implement D7 shapers + wrappers.

**Verify**: build exit 0; test → the 6 new Facade tests green, 0 new
failures.

### Step 3: COM guard-envelope tests (TDD, no Access needed)

1. `ComDdlTest.res`: 6 not-connected tests (pattern `:1153-1193`) asserting
   `{success: false, error: Some("Not connected")}` shapes — for
   `executeSqlScript` also `statementsExecuted: 0` + null fields. RED only
   if Step 1 stubs are wrong; green after (these pin the guards).

**Verify**: build + test green, 0 new failures.

### Step 4: Parser (TDD, pinned against the live Python oracle)

1. Write `parseScriptLines` unit tests in `ComDdlTest.res` (or a new
   `ScriptParserTest.res`): (a) empty/whitespace → `[]`; (b) comment-only
   input (line + block) → `[]`; (c) `"  SELECT 1;"` → text `"SELECT 1"`,
   line 1; (d) two statements across lines with a leading comment and
   mid-statement block comment → exact texts + 1-based lines; (e) final
   statement WITHOUT trailing semicolon → included.
2. Pin expectations against Python FIRST — run:
   `& .venv\Scripts\python.exe -c "import sys; sys.path.insert(0, r'src'); from ms_access_mcp.adapters.wincom import WinComAdapter as W; print(W._parse_script_lines(open(r'rescript-mcp\parity\fixtures\probe_script.sql').read()))"`
   after writing the same fixture string to that temp file (fixture under
   `parity/fixtures/` is NOT in scope — use `$env:TEMP` instead and pass
   the path). Copy Python's exact output into the test assertions.
3. Implement D5 parser. GREEN.

**Verify**: the 5 parser tests green; Python probe output matches test
expectations byte-for-byte (statements AND line numbers).

### Step 5: COM linked-table implementations

Replace the Step 1 stubs with the D6 bodies (get → create → refresh →
recreate → unlink order; `_stripPassword`/`_classifyConnectType` first).
Add ONE real-COM probe-gated test in `ComDdlTest.res` chaining
create → get (assert one entry, name/source_table/connect prefix/type
"Access") → refresh → recreate (source becomes "customers") → unlink →
get returns without it (pattern `:1196-1250`, Access-unavailable skip).

**Verify**: build + test green (real-COM test passes with Access present,
skips otherwise); `Get-Process MSACCESS` → 0 leftovers after the suite.

### Step 6: COM `executeSqlScript` implementation

D6 body (guards already pinned in Step 3). Real-COM probe-gated test:
write the D9 script to `$env:TEMP`, connect to a COPY of northwind
(`Copy-Item` to temp first — never the fixture), assert
`statementsExecuted == 3`, `success == true`, null failing fields, then
`deleteTable("ParityScriptTest")` cleanup + disconnect.

**Verify**: test green; `Get-Process MSACCESS` → 0; temp copy removed.

### Step 7: Harness wiring

`runRescript.ts` (6 dispatch cases + D9 placeholders), `facade.d.ts` (D8),
`run.ts` (`PARITY_SOURCE_DB` in pinnedEnv + fail-fast), `parity_driver.py`
(D10), `cases.schema.json` (D11).

**Verify**: `cmd.exe /c "pnpm -C rescript-mcp build"` exit 0 (compiles the
TS too); quick manual dispatch smoke —
`$env:ACCESS_TEST_DB=...; node rescript-mcp/parity/dist/runRescript.js <a new case file>`
prints the stub envelope on ODBC.

### Step 8: The 12 case files (D12) + validation

No dedicated case-lint script exists (verified — the parity runs are the
lint). Validate shape with:

```
node -e "const fs=require('fs'),p=process.argv[1];const j=JSON.parse(fs.readFileSync(p,'utf8'));const e=JSON.parse(fs.readFileSync('rescript-mcp/parity/cases.schema.json','utf8'));const ops=e.properties.operation.enum;if(!ops.includes(j.operation))throw new Error('op not in enum');if(typeof j.mutating!=='boolean')throw new Error('mutating missing');console.log('OK')"
```

per file (loop it in PowerShell). Then run the three suites.

**Verify**: all 12 files "OK"; `parity:northwind:ddl` → **13 matched + 2
skipped** (7 old + 6 new ODBC error cases); `parity:northwind:com:ddl` →
**14 matched + 1 skipped** (8 old + 6 new COM cases; generate_sql stays
skipped).

### Step 9: Bounded triage (only if Step 8 counts are off)

- Mismatch ONLY at `linked_tables.attributes` (DAO Long signed-int
  representation differs win32com vs winax): add
  `"linked_tables.attributes"` to `volatileFields` of the affected COM
  case with a one-line comment. This is the ONLY auto- permitted volatile.
- Anything else mismatches → record output and STOP (per STOP conditions).

**Verify**: re-run the failing suite → expected counts from Step 8.

### Step 10: Docs + full gates + memory

1. `rescript-mcp/parity/findings.md`: record 038-F-xxx for anything
   discovered (divergences, workarounds); note the deferred
   failing-script case and the MCP-tools deferral.
2. `plans/README.md`: row 038 → DONE with final counts.
3. Full gate sequence (fresh):
   `Get-Process MSACCESS -EA SilentlyContinue | Stop-Process -Force`;
   `clean:all` → `build` → `test` (0 new failures beyond the 9 pre-existing,
   total ≥ 774) → `parity:northwind` (9/9) → `parity:northwind:ddl`
   (13+2) → `parity:northwind:com:ddl` (14+1) →
   `Get-Process MSACCESS` (0) → `git status -- db/` (both fixtures pristine).

## Test plan

- New unit tests: 6 ODBC stub (Step 1), 6 Facade routing/readonly (Step 2),
  6 COM guard (Step 3), 5 parser (Step 4), 2 real-COM probe-gated
  (Steps 5-6). Structural: InstancesTest 22 → 28.
- Models: `OdbcAdapterDdlTest.res` (stub/DDL), `FacadeTest.res:2153-2237`
  (routing), `ComDdlTest.res:1153-1250` (guards + real-COM skip pattern).
- Parity: 12 new case files (D12) — the differential proof.
- Regression: the three parity suites at the Step 8 expected counts.

## Done criteria (ALL must hold)

- [ ] `cmd.exe /c "pnpm -C rescript-mcp clean:all"` + `build` → exit 0
- [ ] `cmd.exe /c "pnpm -C rescript-mcp test"` → exactly the 9 pre-existing
      failures, 0 new; total tests ≥ 774
- [ ] `parity:northwind` → 9/9 matched
- [ ] `parity:northwind:ddl` → 13 matched + 2 skipped
- [ ] `parity:northwind:com:ddl` → 14 matched + 1 skipped
- [ ] `git status -- db/` → northwind.accdb AND postgres.accdb pristine
- [ ] `Get-Process MSACCESS` → 0 after every COM-touching gate
- [ ] 12 new case files validate against the enum check (Step 8 command)
- [ ] No files outside the in-scope list modified (`git status`)
- [ ] `plans/README.md` row 038 updated; findings.md updated if findings exist

## STOP conditions

Stop and report (do not improvise) if:

- Drift check fails or any "Current state" excerpt doesn't match live code.
- The fixture probe (Current state §Link source) shows any postgres.accdb
  user table with `linked=True` or a non-empty `Connect` — the fixture
  assumption is false; do not proceed with `REPLACE_SOURCE_DB`.
- `set(tdef, "Attributes", VInt(2147483648))` AND `VInt(-2147483648)` both
  fail on a real COM connection.
- The `:2410-2411` object-argument Append pattern fails for `TableDefs.Append`
  (works for Relations but not TableDefs).
- Parser test expectations diverge from the live Python
  `_parse_script_lines` probe on ANY pinned case (statements or line
  numbers) — do not adjust expectations by hand; investigate first.
- A parity mismatch outside `linked_tables.attributes` (Step 9's only
  permitted volatile).
- Any new suite failure beyond the 9 pre-existing, twice, after a
  reasonable fix attempt.
- A fix appears to require touching an out-of-scope file.

## Maintenance notes

- `attributes` values on linked tables are DAO 32-bit signed Longs; win32com
  and winax may render the sign differently — that is why
  `linked_tables.attributes` is the pre-authorized volatile. If a consumer
  ever needs exact bits, normalize with `value >>> 0` on both sides.
- Every ADO `Execute` in `executeSqlScript` MUST release the returned
  Recordset envelope — a leak holds DB locks and reproduces the
  MSACCESS-livelock class of bugs from plan 033.
- `PARITY_SOURCE_DB` is now part of the parity env contract (run.ts owns
  it); new linked-table cases should keep using `REPLACE_SOURCE_DB`.
- Deferred on purpose: failing-script parity case (ADO error codes) and MCP
  tool exposure of the 6 ops. Revisit after plans 037a–e decide the tool
  surface question.
- If `db/postgres.accdb` is ever regenerated, it must keep `categories`
  and `customers` as LOCAL tables (the two cases depend on them).
