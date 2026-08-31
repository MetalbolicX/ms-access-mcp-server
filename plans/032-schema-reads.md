# Plan 032: Implement DAO Schema Reads (tables, indexes, relationships, queries, statistics)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.

## Status

- **Priority**: P0 (resolves 3 errored parity cases; foundation for mutations and DDL)
- **Effort**: L (multiple schema APIs)
- **Risk**: LOW–MED
- **Depends on**: plans/031-execute-query.md (DONE, tip `e43bb71`)
- **Category**: feature
- **Planned at**: commit `e43bb71`, 2026-08-31

## Why

The 3 currently-erroring parity cases (`get_table_schema-Customers/Orders/Products.json`) document the missing schema-read APIs on the COM adapter. Plan 031 landed executeQuery (data reads); plan 032 lands structural reads (tables/indexes/relations/queries/statistics). These APIs are prerequisites for mutations (plan 033) and DDL (plan 034). They also unblock the bulk of MCP tools (`get_tables`, `get_table_schema`, `get_indexes`, `get_relationships`, etc.).

## Current state (verified at `e43bb71`)

### Stubbed functions in `ComDataAdapter.res`

All return empty arrays or stub values:

| Function | Line | Current behavior |
|---|---|---|
| `getTables` | 523 | delegates to `_getTablesImpl(self, false)` — stub below |
| `getSystemTables` | 527 | delegates to `_getTablesImpl(self, true)` — stub below |
| `getIndexes` | 611 | `Promise.resolve(Ok([]))` |
| `getRelationships` | 546 | `_getRelationshipsImpl` returns `Ok([])` always |
| `getQueries` | 583 | `_getQueriesImpl` returns `Ok([])` always |
| `getDatabaseStatistics` | 570 | `_getDbStatsImpl` returns minimal dict (path + connected flag only) |

`_getTablesImpl` (lines ~507-519) is also a stub: it checks `isConnected` and returns `Ok([])`.

### Python reference — `SchemaInspector` in `wincom.py`

The Python side delegates to `SchemaInspector` via `_schema`. Key methods:

**`get_tables` (line ~900 in wincom.py):**
```python
def get_tables(self):
    tables = []
    for td in self._db.TableDefs:
        name = td.Name
        if name.startswith('MSys') or name.startswith('~'):
            continue
        tables.append(TableInfo(name=name, type='TABLE', source='LOCAL'))
    return tables
```

**`get_indexes(table_name)` (~line 960):**
```python
def get_indexes(self, table_name):
    for td in self._db.TableDefs:
        if td.Name != table_name:
            continue
        indexes = []
        for ix in td.Indexes:
            index_info = IndexInfo(
                name=ix.Name,
                table_name=table_name,
                fields=[f.Name for f in ix.Fields],
                primary=ix.Primary,
                unique=ix.Unique,
                ignore_nulls=bool(ix.IgnoreNulls),
            )
            indexes.append(index_info)
        return indexes
    return []
```

**`get_relationships` (~line 1000):**
```python
def get_relationships(self):
    rels = []
    for rel in self._db.Relations:
        rels.append(RelationshipInfo(
            name=rel.Name,
            table=rel.Table,
            foreign_table=rel.ForeignTable,
            attributes=rel.Attributes,  # Jet cascading flags
            fields=[f.Name for f in rel.Fields],
        ))
    return rels
```

**`get_queries` (~line 1020):**
```python
def get_queries(self):
    queries = []
    for qd in self._db.QueryDefs:
        queries.append(QueryInfo(
            name=qd.Name,
            sql=qd.SQL,
            type='SELECT' if qd.Type == 0 else 'ACTION',  # DAO query type
        ))
    return queries
```

**`get_database_statistics` (~line 1050):**
```python
def get_database_statistics(self):
    return {
        "objects": {
            "tables": self._db.TableDefs.Count,
            "queries": self._db.QueryDefs.Count,
            "forms": 0, "reports": 0, "macros": 0, "modules": 0,
        },
        "file": {
            "name": self._db.Name,
            "size_bytes": os.path.getsize(self._db.Name) if exists,
            "modified": datetime.fromtimestamp(mtime).isoformat() if exists else "",
        },
        "system": {"access_version": version, "com_available": True},
    }
```

### winax proxy semantics (from plan 030/031)

- `obj[prop]` reads a property
- `obj.method(args)` calls a method
- `WINAX_BINDING.getCount(collection)` — returns count of items in a collection
- `WINAX_BINDING.getItem(collection, VInt(index))` — returns item at index
- `WINAX_BINDING.invokeAsObject(db, "OpenRecordset", [sql])` — method returning COM handle
- `WINAX_BINDING.release(handle)` — release COM handle
- `session.currentDb` — envelope-wrapped DAO Database handle (from plan 029)
- `session.handles.accessApp` — Access Application handle

### ReScript types to produce

From `Interfaces.res`:
- `tableInfo`: `{name: string, type: string, source: string}` — note: `source` field present
- `indexInfo`: `{name: string, table_name: string, fields: array<string>, primary: bool, unique: bool, ignore_nulls: bool}`
- `relationshipInfo`: `{name: string, table: string, foreign_table: string, attributes: int, fields: array<string>}`
- `queryInfo`: `{name: string, sql: string, type: string}`

## Commands

| Purpose | Command | Expected |
|---|---|---|
| Clean+build | `pnpm -C rescript-mcp clean:all && pnpm -C rescript-mcp build` | exit 0 |
| Test | `pnpm -C rescript-mcp test` | all pass, ≥ 728+N |
| Parity | `$env:ACCESS_TEST_ASSUME_ACE="1"; pnpm -C rescript-mcp parity:northwind` | ≥ 8 matched / 0 mismatched / ≤ 1 errored |
| Orphan check | `tasklist /FI "IMAGENAME eq MSACCESS.EXE"` | none after 3+ s settle |

## Scope

**In scope**:
- `plans/032-schema-reads.md` (this file)
- `rescript-mcp/src/Adapters/ComDataAdapter.res` — replace stubs for `_getTablesImpl`, `_getRelationshipsImpl`, `_getQueriesImpl`, `getIndexes`, `_getDbStatsImpl`
- `rescript-mcp/test/ComSchemaReadsTest.res` (new file) — at least 4 real-COM tests (tables, indexes, relationships, queries)
- `rescript-mcp/parity/findings.md` — append 028-F-001 follow-up note
- `plans/README.md` — row 032

**Out of scope**:
- `generate_sql` (SQL generator — deferred to plan 033+)
- `get_modules`, `get_vba_code` (VBA — handled in ComVba.res)
- DDL/mutations (`create_table`, `insert_data`, etc. — plans 033-034)
- ODBC metadata queries — n/a for Access DAO
- `ComSession.res`, `ComUi.res`, `ComVba.res`, `winaxBinding.mjs/.mts`, `Winax.res`

## Git workflow

- Branch: `rescript/032-schema-reads` from `e43bb71`
- Commit 1: `feat(rescript-mcp): implement DAO schema reads (tables, indexes, relationships, queries, statistics)`
- Commit 2: `test(rescript-mcp): add real-COM schema reads integration tests`
- Commit 3: `docs(parity): record 028-F-001 follow-up (schema reads landed)`
- Commit 4: `docs(plans): mark 032 done`
- Conventional commits, no AI attribution, no push, no PR.

## Steps

### Step 1: Verify clean state

```bash
git rev-parse --short HEAD        # expect: e43bb71
git status --short                # only untracked junk files
git checkout -b rescript/032-schema-reads
```

### Step 2: Implement `_getTablesImpl` in `ComDataAdapter.res`

Replace the stub `_getTablesImpl` (around lines 507-519) with:

```
_getTablesImpl: (self: t, systemTables: bool) => Promise.t<result<array<Interfaces.tableInfo>, Errors.t>>

Logic:
1. Guard: if not connected → return Ok([])
2. Get currentDb from session (session.currentDb)
3. Get TableDefs collection: WINAX_BINDING.get(currentDb, "TableDefs")
4. Get count: WINAX_BINDING.getCount(tableDefs)
5. Iterate i in 0..count-1:
   - item = WINAX_BINDING.getItem(tableDefs, VInt(i))
   - name = WINAX_BINDING.get(item, "Name") → string
   - type_ = WINAX_BINDING.get(item, "Type") → int (DAO table type enum)
   - system: name starts with "MSys" or "~" or "~$"
   - Skip: if systemTables=false AND (system OR name starts with "~") → continue
   - Skip: if systemTables=true AND NOT system → continue
   - Append {name, type: "TABLE" (or "SYSTEM" for MSys*), source: "LOCAL"}
   - WINAX_BINDING.release(item)
6. WINAX_BINDING.release(tableDefs)
7. Return Ok(array)

DAO Type enum values (from Access object model):
  - 1 = TABLE (local table)
  - 5 = SYSTEM (MSys* table)
  - 8 = QUERY (saved query — skip in getTables)
For getTables: include type=1 only (skip system tables)
For getSystemTables: include type=5 only (MSys* tables)
```

**Critical reminders**:
- Filter `~` prefix (temp tables like `~TMP_MyTable`)
- Filter `MSys*` (system tables)
- Filter `~$` (temp shadow files)
- Use `WINAX_BINDING.release(item)` after each TableDef to avoid leaks
- Use `WINAX_BINDING.release(tableDefs)` after iteration

### Step 3: Implement `getIndexes` in `ComDataAdapter.res`

Replace `getIndexes` stub (line 611-613):

```
Logic:
1. Guard: if not connected → return Ok([])
2. Get currentDb from session
3. Get TableDefs: WINAX_BINDING.get(currentDb, "TableDefs")
4. Find target table by iterating TableDefs:
   - For each TableDef: if name === tableName, found
   - If not found: return Ok([])
5. Get Indexes collection from TableDef: WINAX_BINDING.get(tableDef, "Indexes")
6. Iterate Indexes:
   - For each Index:
     - name = get(index, "Name")
     - primary = get(index, "Primary") → bool
     - unique = get(index, "Unique") → bool
     - ignore_nulls = get(index, "IgnoreNulls") → bool
     - fields collection = get(index, "Fields")
     - fieldCount = getCount(fields)
     - fieldNames = [] then for j in 0..fieldCount-1:
         f = getItem(fields, VInt(j))
         fname = get(f, "Name")
         push fname; release f
     - release fields collection
     - Append {name, table_name: tableName, fields: fieldNames, primary, unique, ignore_nulls}
7. Release Indexes, release tableDef, release TableDefs
8. Return Ok(indexes array)
```

### Step 4: Implement `_getRelationshipsImpl` in `ComDataAdapter.res`

Replace `_getRelationshipsImpl` stub (lines 535-544):

```
Logic:
1. Guard: if not connected → return Ok([])
2. Get currentDb from session
3. Get Relations collection: WINAX_BINDING.get(currentDb, "Relations")
4. Get count: WINAX_BINDING.getCount(relations)
5. Iterate i in 0..count-1:
   - rel = WINAX_BINDING.getItem(relations, VInt(i))
   - name = get(rel, "Name")
   - table = get(rel, "Table")
   - foreign_table = get(rel, "ForeignTable")
   - attributes = get(rel, "Attributes") → int (cascading flags)
   - fields collection = get(rel, "Fields")
   - fieldCount = getCount(fields)
   - fieldNames = [] then for j in 0..fieldCount-1:
       f = getItem(fields, VInt(j))
       fname = get(f, "Name")
       push fname; release f
   - release fields collection
   - Append {name, table, foreign_table, attributes, fields: fieldNames}
   - release rel
6. WINAX_BINDING.release(relations)
7. Return Ok(array)
```

### Step 5: Implement `_getQueriesImpl` in `ComDataAdapter.res`

Replace `_getQueriesImpl` stub (lines 574-581):

```
Logic:
1. Guard: if not connected → return Ok([])
2. Get currentDb from session
3. Get QueryDefs collection: WINAX_BINDING.get(currentDb, "QueryDefs")
4. Get count: WINAX_BINDING.getCount(queryDefs)
5. Iterate i in 0..count-1:
   - qd = WINAX_BINDING.getItem(queryDefs, VInt(i))
   - name = get(qd, "Name")
   - Skip if name starts with "~" (temp query)
   - sql = get(qd, "SQL") → string
   - type_val = get(qd, "Type") → int
     - 0 = SELECT (dbQryDefTypeSelect = 0)
     - Otherwise = ACTION
   - type_str = if type_val === 0 then "SELECT" else "ACTION"
   - Append {name, sql, type: type_str}
   - release qd
6. WINAX_BINDING.release(queryDefs)
7. Return Ok(array)
```

### Step 6: Implement `_getDbStatsImpl` in `ComDataAdapter.res`

Replace `_getDbStatsImpl` stub (lines 558-568) with richer stats:

```
Logic:
1. Build stats dict
2. If connected and dbPath is known:
   - objects.tables = count from TableDefs
   - objects.queries = count from QueryDefs
   - objects.forms/reports/macros/modules = 0 (not available without Access UI)
   - file.name = dbPath
   - file.size_bytes = 0 (file system op requires async — skip or store 0)
   - file.modified = "" (same)
   - system.access_version = from session handles app version
   - system.com_available = true
3. If not connected: return minimal dict with connected=false
4. Return Ok(dict)
```

### Step 7: Write `ComSchemaReadsTest.res`

Create `rescript-mcp/test/ComSchemaReadsTest.res` with probe-gated tests:

**Test A (real-COM): `getTables` on test_db.accdb**
- Probe gate: try to open Access + get currentDb; skip if fails
- Call `getTables` from `DaoAdapter.asInstance(adapter).getTables`
- Assert: `success=true`, array contains `Customers`, `Orders`, `Products`
- Assert: no MSys* tables, no ~* tables

**Test B (real-COM): `getIndexes` for Customers**
- Probe gate same as above
- Call `getIndexes(adapter, "Customers")`
- Assert: returns array (may be empty if no explicit indexes beyond PK)
- Assert each index has `name`, `table_name`, `fields`, `primary`, `unique`

**Test C (real-COM): `getRelationships` on test_db.accdb**
- Probe gate same as above
- Call `getRelationships(adapter)`
- Assert: returns array (may be empty if no FKs defined in fixture)
- Graceful empty is OK — just verify shape

**Test D (real-COM): `getQueries` on test_db.accdb**
- Probe gate same as above
- Call `getQueries(adapter)`
- Assert: returns array (may be empty)
- Each item has `name`, `sql`, `type`

**Test E (real-COM): `getDatabaseStatistics`**
- Probe gate same as above
- Call `getDatabaseStatistics(adapter)`
- Assert: `success=true`, dict has `objects.tables >= 3`, `objects.queries >= 0`

### Step 8: Build and test

```bash
pnpm -C rescript-mcp clean:all
pnpm -C rescript-mcp build
pnpm -C rescript-mcp test
```

Expected: all pass, test count ≥ 728+N.

### Step 9: Parity run

```bash
$env:ACCESS_TEST_ASSUME_ACE="1"; pnpm -C rescript-mcp parity:northwind
```

Verify: at least 8 matched / 0 mismatched / ≤ 1 errored. The 3 get_table_schema cases should now at least not error.

### Step 10: Record 028-F-001 follow-up

Append to `rescript-mcp/parity/findings.md`:

```markdown
## 028-F-001 Follow-up (plan 032)

Schema reads landed in plan 032. The 3 previously-errored parity cases
(`get_table_schema-Customers/Orders/Products.json`) now resolve via the
implemented `getTables`, `getIndexes`, `getRelationships` DAO calls.
```

### Step 11: Closeout

Update `plans/README.md` row 032 → DONE (final SHA, test count, note about parity improvement).

Commit `docs(plans): mark 032 done`.

## Test plan

Minimum 4 new real-COM probe-gated tests (A–D), plus optional E for stats.

## Done criteria

- [ ] All stubbed schema-read functions in `ComDataAdapter.res` now return real data
- [ ] At least 4 new real-COM tests added
- [ ] Suite ≥ 732 passing; 0 failing
- [ ] Parity: ≥ 8 matched / 0 mismatched / ≤ 1 errored (was 6/0/3 — expect at least 2 of the 3 schema cases to flip to matched)
- [ ] Plan 032 file exists and is self-contained
- [ ] README row 032 → DONE
- [ ] `028-F-001` follow-up appended to `rescript-mcp/parity/findings.md`
- [ ] No orphan MSACCESS.EXE; 0 dirty files in `git status` except junk
- [ ] Conventional commits only; no push; no PR

## STOP conditions

- DAO collection iteration differs materially from assumed (e.g. Fields is not iterable via getCount/getItem) — verify with live probe before implementing more
- A backward-compat signature change is required elsewhere — STOP and report
- Existing test regresses (any pre-732 test)
- Parity MISMATCH on a previously-passing case
- Hangs > 60 s or MSACCESS orphan > 10 s after suite
- Drift check shows files outside the in-scope list
