# Plan 044 Phase 0 Inventory

## Reconciled surface

- Python has **142** `@mcp.tool()` decorators in **18** modules. `server.py:122`
  is a comment, not a decorator. Every Python tool is served by FastMCP; there
  is no per-decorator transport or gate. Global gates are HTTP-only
  `ApiKeyMiddleware` (`src/ms_access_mcp/auth.py:23`,
  `ACCESS_MCP_API_KEY`) and `ReadOnlyMiddleware`
  (`src/ms_access_mcp/auth.py:218`, `ACCESS_MCP_READ_ONLY=true`).
- The ReScript facade has **33** public methods (plus 14 internal helpers) in
  `rescript-mcp/src/Services/Facade.res`. `Server.res:319-393` registers **12**
  MCP tools. `Server.res:315` says 11 and is stale.
- The parity corpus has **62** cases: root 17, northwind 9, northwind/ddl 15,
  northwind/com 6, and northwind/com/ddl 15. Cases select `operation` and
  `variant: odbc|com`; case existence is not live acceptance evidence.

`MCP exposed?` is deliberately a wiring classification, not a success claim:
`yes` is registered; `orphaned-callback` has a callback factory but is absent
from `tools[]`; `unwired-facade-op` has no callback; `facade+case-only` is
called directly by the parity composition path, not the running MCP server;
and `parity-only` means a case has no facade method.

| Operation | Python entrypoint / global gates | ReScript facade | MCP exposed? | Backend | Case / status / next acceptance test |
|---|---|---|---|---|---|
| connect_access | `mcp/connection.py:56-100`; FastMCP, HTTP auth/readonly globals | `Facade.res:196`; `Server.res:85-95,323-327` | yes | ODBC/COM | Cases exist; **implemented-unverified**. Stdio registration plus ODBC/COM identity test. |
| disconnect_access | `mcp/connection.py:214-226` | `Facade.res:262`; `Server.res:98-104,329-333` | yes | pool/ODBC/COM | **implemented-unverified**. Ownership/cleanup contract test. |
| list_connections | `mcp/connection.py:229-251` | `Facade.res:299`; `Server.res:107-111,335-339` | yes | pool | **implemented-unverified**. Stdio list test. |
| is_connected | `mcp/connection.py:280-291` | `Facade.res:342`; `Server.res:114-120,341-345` | yes | pool | **implemented-unverified**. Stdio connection-state test. |
| query_data | `mcp/crud.py:222-241` | `Facade.res:406`; `Server.res:139-150,347-351` | yes | ODBC/COM | Cases exist; **implemented-unverified**. Exact-case ODBC/COM result contract. |
| insert_data | `mcp/crud.py:244-263` | `Facade.res:442`; `Server.res:154-165,353-357` | yes | ODBC/COM | Cases exist; **implemented-unverified**. Isolated mutation/read-back. |
| update_data | `mcp/crud.py:266-295` | `Facade.res:503`; `Server.res:168-193,359-363` | yes | ODBC/COM | **implemented-unverified**. Confirm/dry-run contract on disposable DB. |
| delete_data | `mcp/crud.py:298-319` | `Facade.res:576`; `Server.res:197-217,365-369` | yes | ODBC/COM | **implemented-unverified**. Confirm/WHERE/read-back contract. |
| get_tables | `mcp/schema.py:40-50` | `Facade.res:632`; `Server.res:221-227,371-375` | yes | ODBC/COM | Cases exist; **implemented-unverified**. Exact-case schema result. |
| get_table_schema | `mcp/schema.py:73-88` | `Facade.res:686`; `Server.res:230-241,377-381` | yes | ODBC/COM | **implemented-unverified**. Blank-name and schema contract. |
| get_queries | `mcp/crud.py:37-46` | `Facade.res:782`; `Server.res:244-250,383-387` | yes | ODBC/COM | **implemented-unverified**. Exact-case saved-query result. |
| execute_raw_sql | `mcp/raw_sql.py:23-55` | `Facade.res:1273`; `Server.res:253-279,389-393` | yes | ODBC/COM | Cases exist; **implemented-unverified**. Dangerous-SQL guard and isolated postcondition. |
| set_active_connection | `mcp/connection.py:254-266` | `Facade.res:371`; callback `Server.res:123-130` | orphaned-callback | pool | **implemented-unverified**. Register then stdio active-pointer test. |
| get_active_connection | `mcp/connection.py:269-277` | `Facade.res:392`; callback `Server.res:132-137` | orphaned-callback | pool | **implemented-unverified**. Register then stdio active-pointer test. |
| get_relationships | `mcp/schema.py:91-107` | `Facade.res:742`; callback `Server.res:282-289` | orphaned-callback | ODBC/COM | **implemented-unverified**. Register plus relationship contract. |
| get_database_statistics | `mcp/schema.py:189-209` | `Facade.res:819`; callback `Server.res:291-298` | orphaned-callback | ODBC/COM | **implemented-unverified**. Register plus statistics shape test. |
| export_data | `mcp/export.py:36-103` | `Facade.res:1501`; callback `Server.res:300-311` | orphaned-callback | ODBC/COM | **implemented-unverified**. Register plus allowed-path/export-content test. |
| create_table | Python schema surface | `Facade.res:986` | facade+case-only | ODBC/COM | **implemented-unverified**. Disposable DDL/read-back. |
| delete_table | Python schema surface | `Facade.res:1008` | facade+case-only | ODBC/COM | **implemented-unverified**. Disposable DDL/read-back. |
| alter_table | Python schema surface | `Facade.res:1029` | facade+case-only | ODBC/COM | **implemented-unverified**. Exact operation/error contract. |
| create_index / drop_index / get_indexes | Python schema surface | `Facade.res:1107,1131,1152` | facade+case-only | DAO/ODBC where supported | **implemented-unverified**. DDL/read-back and unsupported-backend contract. |
| set_query_sql / delete_query | Python query surface | `Facade.res:1187,1208` | facade+case-only | DAO/ODBC where supported | **implemented-unverified**. Saved-query read-back. |
| create_query | `mcp/crud.py:51` | `Facade.res:1231` | unwired-facade-op | DAO/ODBC | **implemented-unverified**: no parity case. Add positive/duplicate/cleanup case. |
| generate_sql | `mcp/schema.py:110-137` | `Facade.res:1252` | facade+case-only | schema/DAO | **implemented-unverified**. Isolated generated-file and fixture-immutability test. |
| get_linked_tables | `mcp/linked_tables.py` | `Facade.res:1374` | facade+case-only | COM/DAO | **stubbed**: connected adapter returns empty success (`ComDataAdapter.res:2752-2759`). DAO enumeration/read-back. |
| create_linked_table | `mcp/linked_tables.py` | `Facade.res:1388` | facade+case-only | COM/DAO | **implemented-unverified**. Create plus independent DAO read-back. |
| refresh_linked_table | `mcp/linked_tables.py` | `Facade.res:1410` | facade+case-only | COM/DAO | **implemented-unverified**. Refresh/queryable postcondition. |
| recreate_linked_table | Python name differs: `mcp/linked_tables.py:229` is `upsert_linked_table` | `Facade.res:1435` | facade+case-only | COM/DAO | **crosswalk-required**. Decide rename/alias/semantic equivalence, then recreate postcondition. |
| unlink_table | `mcp/linked_tables.py` | `Facade.res:1462` | facade+case-only | COM/DAO | **implemented-unverified**. Removal/read-back. |
| execute_sql_script | `mcp/persistence.py:371` | `Facade.res:1482` | facade+case-only | COM/DAO; ODBC raises unsupported | **implemented-unverified**. Script success/failing-line/ODBC-unsupported contract. |

No `parity-only` row is asserted: the authoritative Phase-0 facts establish 62
case files but do not identify a case operation lacking a facade method. This
remains a Phase-1 exact-case reconciliation check, not a fabricated mapping.

## Known gaps

1. **Missing `create_query` case:** Python `mcp/crud.py:51` and
   `Facade.res:1231` exist, but no JSON case exists. Status is
   `implemented-unverified`.
2. **Linked-table crosswalk mismatch:** parity/facade use
   `recreate_linked_table` (`Facade.res:1435`); Python exposes
   `upsert_linked_table` (`mcp/linked_tables.py:229`). There is no Python
   `recreate_linked_table`; decide the semantic crosswalk before acceptance.
3. **SQL-script entrypoint resolved:** Python is
   `mcp/persistence.py:371`; implementations are `adapters/wincom.py:1053`,
   `adapters/odbc.py:483`, and `adapters/com_only_mixin.py:440`; contract is
   `adapters/interfaces.py:77` / `adapters/base.py:195`; registry import is
   `mcp/server.py:242`.
4. **Wiring deficit:** five orphaned callback factories (`Server.res:123,132,
   282,291,300`) plus 16 facade operations without callback factories leave
   21 facade operations reachable only through the parity composition path,
   not the running MCP server.
5. **Plan count correction:** `@mcp.tool()` is 142 across 18 modules, not
   143 across 19; `mcp/server.py:122` is a comment.
6. **Python-only surface:** approximately 110 Python tools have no ReScript
   facade or parity case: `com.py:24`, `reports.py:17`, `persistence.py:16`,
   `dev_copy.py:15`, `vba.py:14`, `macros.py:7`, `migration.py:4`,
   `db_properties.py:2`, `recovery.py:2`, `system.py:2`, and `analysis.py:1`.
   Their status is **missing**.

## Acceptance B follow-on work units (ordered)

| Work unit / operation family | Target backend guess | Next acceptance test |
|---|---|---|
| `com.*` (24 tools), then `vba.*` (14), `macros.*` (7), `reports.*` (17) | Windows COM/Access only | Capability-gated disposable-DB integration test per operation, including a no-COM unsupported contract. |
| `persistence.*` (16, including SQL-script-adjacent work), `migration.*` (4), `db_properties.*` (2) | DAO/COM; ODBC only where Python supports it | Operation-specific ODBC/COM contract and isolated read-back; unsupported ODBC is an asserted result. |
| `dev_copy.*` (15), `recovery.*` (2), `system.*` (2) | filesystem/Windows plus COM where invoked | Absolute allowed-directory test using disposable copies, with hash-preservation assertions. |
| `analysis.*` (1) | ODBC/COM data path | Exact result-shape test against a disposable fixture. |

The module-family notation is intentional: Phase 0 has verified the published
counts, not invented individual tool names. Phase 1 must enumerate the FastMCP
runtime list before these work units are split into implementation tickets.

## Counts and Phase-0 gate

- Inventory rows: **33** facade operations — 12 `yes`, 5
  `orphaned-callback`, 1 `unwired-facade-op`, and 15 `facade+case-only`.
- Statuses: **31 implemented-unverified, 1 stubbed, 1 crosswalk-required**.
- Gap classes: **6** (one each: missing case, naming crosswalk, resolved
  entrypoint provenance, wiring deficit, count correction, Python-only
  surface). The wiring class contains 21 operations; the Python-only class is
  approximately 110 tools.

This is a Phase-0 inventory, not live acceptance. Every currently declared
Acceptance-A facade operation has a row; the Phase-1 runtime enumeration must
resolve the intentionally unasserted `parity-only` mapping before any full
replacement claim.
