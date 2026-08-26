#!/usr/bin/env python3
"""Inventory tests/integration/fixtures/test_db.accdb via probe-based discovery.

Access ACE-ODBC ACL-blocks MSysObjects for non-admin users (ODBC error
-1907, "no read permission on MSysObjects"), so the canonical schema-query
path is unavailable. We instead probe a curated candidate list and treat a
successful no-row SELECT as "this name is a real user table".

Environment overrides:
  ACCESS_TEST_DB                  - fixture path
  ACCESS_FIXTURE_TABLE_CANDIDATES - semicolon-separated candidate names

Outputs:
  - Markdown at rescript-mcp/parity/fixture-inventory.md
  - One JSON line to stdout summarizing counts.

Exit codes: 0 success; 1 connection failure or zero tables (STOP);
2 bad arguments.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import TypedDict

import pyodbc

DRIVER = "Microsoft Access Driver (*.mdb, *.accdb)"
DEFAULT_FIXTURE = Path(
    r"D:\code\python\ms-access-mcp-server\tests\integration\fixtures\test_db.accdb"
)
OUTPUT_MD = Path(
    r"D:\code\python\ms-access-mcp-server\rescript-mcp\parity\fixture-inventory.md"
)

# Northwind + Northwind-lite + common variants. Broader than the canonical
# 3-table fixture on purpose so future fixtures still get discovered.
DEFAULT_CANDIDATES: list[str] = [
    "AlphabeticalListOfProducts", "Categories", "CategorySalesFor1997",
    "Contacts", "CurrentProductList", "CustomerAndSuppliersByCity",
    "CustomerCustomerDemo", "Customers", "Employees", "Inventory",
    "InventoryTransactions", "OrderDetails", "OrderItems", "Orders",
    "Products", "ProductsAboveAveragePrice", "ProductsByCategory",
    "PurchaseOrderDetails", "PurchaseOrders", "QuarterlyOrders",
    "Regions", "SalesByCategory", "Shippers", "SummaryOfSalesByQuarter",
    "SummaryOfSalesByYear", "Suppliers", "TenMostExpensiveProducts",
    "Territories",
]

# pyodbc via the ACE ODBC driver reports cursor.description[i][1] as the
# Python conversion class (e.g. <class 'int'>). Map to readable Access names.
PYTHON_TYPE_NAMES: dict[type, str] = {
    int:          "integer",  # Access Long Integer
    float:        "double",   # Access Double (or Single)
    str:          "string",   # Access Text
    bytes:        "binary",   # Access OLE Object / binary
    bool:         "boolean",  # Access YesNo
    _dt.datetime: "datetime", _dt.date: "date", _dt.time: "time",
}


class _Column(TypedDict):
    name: str
    type: str
    nullable: bool


class _Table(TypedDict):
    columns: list[_Column]
    row_count: int | None


def _type_name(code: object) -> str:
    if isinstance(code, type):
        # bool is a subclass of int -- match it first to avoid mapping True -> SQL_BIT.
        if code is bool:
            return "boolean"
        return PYTHON_TYPE_NAMES.get(code, f"pytype_{code.__name__}")
    if isinstance(code, int) and not isinstance(code, bool):
        # Fallback for ODBC drivers that report integer SQL type codes.
        fbk = {4: "integer", 5: "smallint", 8: "double", 12: "string",
               -1: "memo", -7: "boolean", -9: "string", 11: "datetime"}
        return fbk.get(code, f"odbc_type_{code}")
    return "unknown"


def _resolve_db_path() -> Path:
    env = os.environ.get("ACCESS_TEST_DB", "").strip()
    return Path(env) if env else DEFAULT_FIXTURE


def _resolve_candidates() -> list[str]:
    env = os.environ.get("ACCESS_FIXTURE_TABLE_CANDIDATES", "").strip()
    if not env:
        return list(DEFAULT_CANDIDATES)
    return [n.strip() for n in env.split(";") if n.strip()]


def _connect(db_path: Path) -> pyodbc.Connection:
    return pyodbc.connect(f"Driver={{{DRIVER}}};DBQ={db_path};")


def _table_exists(conn: pyodbc.Connection, name: str) -> bool:
    """Probe whether `[name]` resolves to a user-table. Swallows any ODBC
    error (ACL blocks, 'not found') and returns False.
    """
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM [{name}] WHERE 1=0")
        ok = bool(cur.description)
        cur.close()
        return ok
    except pyodbc.Error:
        return False


def _inspect_table(conn: pyodbc.Connection, name: str) -> _Table:
    cols: list[_Column] = []
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM [{name}] WHERE 1=0")
    for col in cur.description or ():
        # description tuple: (name, type_code, display_size,
        #                    internal_size, precision, scale, null_ok)
        null_ok = bool(col[6]) if len(col) > 6 else True
        cols.append({"name": str(col[0]), "type": _type_name(col[1]),
                     "nullable": null_ok})
    cur.close()

    cnt = conn.cursor()
    row = cnt.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()
    cnt.close()
    return {"columns": cols,
            "row_count": None if row is None else int(row[0])}


def _infer_fk_relationships(
    tables: list[tuple[str, _Table]],
) -> list[tuple[str, str, str]]:
    """Heuristic: a column ending in `ID` (other than its own table's `ID`
    primary key) is treated as a foreign key referencing `<table>.ID`.

    Stem matching tolerates singular/plural (``Customer`` <-> ``Customers``).
    Returns sorted ``(table, column, referenced_table)`` tuples.
    """
    pks: set[str] = {t for t, m in tables
                     if m["columns"] and m["columns"][0]["name"] == "ID"}

    def _resolve(stem: str) -> str | None:
        if stem in pks:
            return stem
        if stem + "s" in pks:
            return stem + "s"
        if stem.endswith("s") and stem[:-1] in pks:
            return stem[:-1]
        return None

    rels: list[tuple[str, str, str]] = []
    for tname, meta in tables:
        for col in meta["columns"]:
            cn = col["name"]
            if not cn.endswith("ID") or cn == "ID" or len(cn) <= 2:
                continue
            ref = _resolve(cn[:-2])
            if ref is not None:
                rels.append((tname, cn, ref))
    rels.sort()
    return rels


def _probe_saved_queries(
    conn: pyodbc.Connection,
) -> tuple[list[str], str | None]:
    try:
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT Name FROM MSysAccessStorage WHERE Type = 5 ORDER BY Name"
        ).fetchall()
        names = [str(r[0]) for r in rows]
        cur.close()
        return names, None
    except pyodbc.Error as exc:
        return [], f"{type(exc).__name__}: {exc}"


def _render_markdown(
    db_path: Path,
    tables: list[tuple[str, _Table]],
    relations: list[tuple[str, str, str]],
    saved_queries: list[str],
    saved_query_error: str | None,
    probed_count: int,
) -> str:
    stat = db_path.stat()
    out: list[str] = []
    p = out.append
    p("# Fixture inventory - tests/integration/fixtures/test_db.accdb")
    p("")
    p(f"Generated: {_dt.datetime.now().isoformat()}")
    p(f"File size: {stat.st_size} bytes")
    p(f"File mtime: {_dt.datetime.fromtimestamp(stat.st_mtime).isoformat()}")
    p("Source: tests/integration/fixtures/test_db.accdb (Python oracle)")
    p(f"Driver: `{DRIVER}` via pyodbc")
    p("")

    p(f"## User tables ({len(tables)})")
    p("")
    for tname, meta in tables:
        rc = "?" if meta["row_count"] is None else str(meta["row_count"])
        p(f"### `{tname}` ({rc} rows)")
        p("")
        if not meta["columns"]:
            p("*(no columns retrieved)*")
            p("")
            continue
        p("| Column | Type | Nullable |")
        p("|--------|------|----------|")
        for c in meta["columns"]:
            ns = "yes" if c["nullable"] else "no"
            p(f"| `{c['name']}` | `{c['type']}` | {ns} |")
        p("")

    p("## Foreign-key relationships (heuristic)")
    p("")
    if relations:
        for tname, col, ref in relations:
            p(f"- `{tname}.{col}` -> `{ref}.ID` (heuristic: column name "
              "ends in `ID`, matches primary key of another table)")
    else:
        p("- (none inferred by the column-name heuristic)")
    p("")

    p(f"## Saved queries ({len(saved_queries)})")
    p("")
    if saved_queries:
        for q in saved_queries:
            p(f"- `{q}`")
    elif saved_query_error:
        p(f"- none detected - `MSysAccessStorage WHERE Type = 5` "
          f"returned error: `{saved_query_error}`")
    else:
        p("- (none detected - `MSysAccessStorage WHERE Type = 5` was "
          "empty for this fixture)")
    p("")

    p("## Notes")
    p("")
    for n in (
        "MSysObjects ACL-blocked by Access (error -1907, \"no read "
        "permission on MSysObjects\") in this fixture; discovery uses "
        "probe-based candidate enumeration instead.",
        "MSysAccessStorage is internal Access workspace scaffolding, not "
        "user tables - verified during plan 016.",
        "Discovery strategy: probe-based candidate enumeration against the "
        "candidate list (env var `ACCESS_FIXTURE_TABLE_CANDIDATES`).",
        "Row counts taken via `SELECT COUNT(*) FROM [<name>]`; columns "
        "via `SELECT * FROM [<name>] WHERE 1=0` + `cur.description`.",
    ):
        p(f"- {n}")
    p(f"- Probed {probed_count} candidate names; override via "
      "`ACCESS_FIXTURE_TABLE_CANDIDATES` (semicolon-separated).")
    p("")
    return "\n".join(out)


def main() -> int:
    db_path = _resolve_db_path()
    if not db_path.exists():
        print(f"ERROR: fixture file not found at {db_path}", file=sys.stderr)
        return 2
    candidates = _resolve_candidates()
    if not candidates:
        print("ERROR: candidate list is empty "
              "(set ACCESS_FIXTURE_TABLE_CANDIDATES or use defaults)",
              file=sys.stderr)
        return 2
    try:
        conn = _connect(db_path)
    except pyodbc.Error as exc:
        print(f"ERROR: pyodbc connection failed: {exc}", file=sys.stderr)
        return 1

    try:
        discovered: list[tuple[str, _Table]] = []
        for cand in candidates:
            if _table_exists(conn, cand):
                discovered.append((cand, _inspect_table(conn, cand)))
        discovered.sort(key=lambda kv: kv[0])

        relations = _infer_fk_relationships(discovered)
        saved_queries, saved_query_error = _probe_saved_queries(conn)

        OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_MD.write_text(
            _render_markdown(db_path, discovered, relations, saved_queries,
                             saved_query_error, probed_count=len(candidates)),
            encoding="utf-8",
        )

        print(json.dumps({
            "tables": [t for t, _ in discovered],
            "queries_count": len(saved_queries),
            "fixture_path": str(db_path),
            "discovered": len(discovered),
            "probed": len(candidates),
        }))

        if not discovered:
            print("STOP: zero user tables discovered", file=sys.stderr)
            return 1
        return 0
    finally:
        try:
            conn.close()
        except pyodbc.Error:
            pass


if __name__ == "__main__":
    sys.exit(main())
