"""E2E tests for query analyzer against live postgres.accdb.

Runs 10 example queries through the real QueryAnalyzerService, validates
results against expectations, and renders a Markdown report at
docs/query-analyzer-examples.md.

Requires Windows + MS Access COM automation (pywin32).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ms_access_mcp.mcp.server import connection_service
from ms_access_mcp.services.query_analyzer import QueryAnalyzerService

# ---- Paths ------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent
DB_PATH = _PROJECT_ROOT / "db" / "postgres.accdb"
DOCS_PATH = _PROJECT_ROOT / "docs" / "query-analyzer-examples.md"

CONNECTION_NAME = "qa_e2e"

# ---- Example queries --------------------------------------------------------
# Each entry: name, description, sql, and expectations to assert.

QUERIES: list[dict[str, Any]] = [
    {
        "name": "Simple SELECT — Baseline",
        "description": "PK lookup, no anti-patterns — should be clean.",
        "sql": "SELECT * FROM customers WHERE customer_id = 1",
        "expect": {"complexity_label": "simple", "max_score": 5},
    },
    {
        "name": "Leading Wildcard LIKE — Anti-pattern",
        "description": (
            "LIKE '%term' on an unindexed column — prevents index usage."
        ),
        "sql": "SELECT * FROM products WHERE product_name LIKE '%Mouse%'",
        "expect": {
            "complexity_label": "simple",
            "max_score": 15,
            "has_leading_wildcard_like": True,
        },
    },
    {
        "name": "Aggregate with Unindexed WHERE — Missing Index",
        "description": "COUNT(*) on a filtered column that has no index.",
        "sql": "SELECT COUNT(*) AS n FROM orders WHERE order_status = 'shipped'",
        "expect": {
            "complexity_label": "simple",
            "max_score": 10,
            "has_aggregates": True,
        },
    },
    {
        "name": "Single JOIN with Unindexed WHERE — Missing Index",
        "description": "One JOIN plus a filter on an unindexed column.",
        "sql": (
            "SELECT c.customer_name, o.order_total "
            "FROM customers c "
            "INNER JOIN orders o ON c.customer_id = o.order_customer_id "
            "WHERE o.order_total > 50"
        ),
        "expect": {
            "complexity_label": "simple",
            "max_score": 15,
            "join_count": 1,
        },
    },
    {
        "name": "Multi-JOIN with Unindexed Email — Complex",
        "description": (
            "3 JOINs across 4 tables with WHERE on unindexed customer_email."
        ),
        "sql": (
            "SELECT c.customer_name, p.product_name, oi.order_item_quantity "
            "FROM customers c "
            "INNER JOIN orders o ON c.customer_id = o.order_customer_id "
            "INNER JOIN order_items oi ON o.order_id = oi.order_item_order_id "
            "INNER JOIN products p ON oi.order_item_product_id = p.product_id "
            "WHERE c.customer_email = 'alice@email.com'"
        ),
        "expect": {
            "complexity_label": "moderate",
            "min_score": 26,
            "join_count": 3,
        },
    },
    {
        "name": "Function in WHERE — Index Prevention",
        "description": (
            "VBA YEAR() function in WHERE — function call prevents index usage."
        ),
        "sql": "SELECT * FROM orders WHERE YEAR(order_date) = 2026",
        "expect": {
            "complexity_label": "simple",
            "max_score": 15,
            "has_where_function": True,
        },
    },
    {
        "name": "Subquery in WHERE — Moderate Complexity",
        "description": "IN (SELECT ...) nested subquery adds to score.",
        "sql": (
            "SELECT product_name FROM products "
            "WHERE product_id IN ("
            "SELECT order_item_product_id FROM order_items "
            "WHERE order_item_quantity > 1"
            ")"
        ),
        "expect": {
            "complexity_label": "moderate",
            "min_score": 20,
            "max_score": 30,
            "has_subquery": True,
        },
    },
    {
        "name": "NOT IN Subquery — Classic Anti-pattern",
        "description": (
            "NOT IN limits query plan options — prefer NOT EXISTS or LEFT JOIN."
        ),
        "sql": (
            "SELECT c.customer_name FROM customers c "
            "WHERE c.customer_id NOT IN ("
            "SELECT order_customer_id FROM orders"
            ")"
        ),
        "expect": {
            "complexity_label": "moderate",
            "min_score": 20,
            "has_not_in": True,
            "has_subquery": True,
        },
    },
    {
        "name": "GROUP BY + HAVING + ORDER BY — Moderate",
        "description": (
            "Join, aggregates, GROUP BY, HAVING, ORDER BY — multiple patterns."
        ),
        "sql": (
            "SELECT c.category_name, COUNT(p.product_id) AS cnt, "
            "AVG(p.product_price) AS avg_price "
            "FROM products p "
            "INNER JOIN categories c ON p.product_category_id = c.category_id "
            "GROUP BY c.category_name "
            "HAVING COUNT(p.product_id) > 1 "
            "ORDER BY cnt DESC"
        ),
        "expect": {
            "complexity_label": "moderate",
            "min_score": 20,
            "max_score": 35,
            "has_aggregates": True,
            "has_group_by": True,
            "has_order_by": True,
        },
    },
    {
        "name": "Cartesian Join — Heavy Anti-pattern",
        "description": (
            "Unqualified FROM with no WHERE/JOIN → cartesian product explosion."
        ),
        "sql": "SELECT * FROM categories, products",
        "expect": {
            "complexity_label": "simple",
            "max_score": 20,
            "has_cartesian_join": True,
        },
    },
]

# ---- Fixture ----------------------------------------------------------------


@pytest.fixture(scope="module")
def com_connection():
    """Connect to postgres.accdb via COM, disconnect on teardown."""
    if not DB_PATH.exists():
        pytest.skip(f"Database not found: {DB_PATH}")

    abs_db_path = str(DB_PATH.resolve())
    connection_service.connect(CONNECTION_NAME, abs_db_path, "com")
    assert connection_service.is_connected(CONNECTION_NAME)
    yield
    try:
        connection_service.disconnect(CONNECTION_NAME)
    except Exception:
        pass


# ---- Helpers ----------------------------------------------------------------


def _check_complexity_expectation(num: int, name: str, expect: dict, complexity: dict) -> None:
    """Assert complexity expectations against the parsed result."""
    label = complexity.get("complexity_label", "")
    score = complexity.get("score", 0)

    if "complexity_label" in expect:
        assert label == expect["complexity_label"], (
            f"Query {num} ({name}): expected complexity={expect['complexity_label']}, got {label}"
        )

    if "min_score" in expect:
        assert score >= expect["min_score"], (
            f"Query {num} ({name}): expected score >= {expect['min_score']}, got {score}"
        )

    if "max_score" in expect:
        assert score <= expect["max_score"], (
            f"Query {num} ({name}): expected score <= {expect['max_score']}, got {score}"
        )

    # Check boolean detection flags
    for key in (
        "has_subquery",
        "has_correlated_subquery",
        "has_leading_wildcard_like",
        "has_where_function",
        "has_cartesian_join",
        "has_not_in",
        "has_aggregates",
        "has_group_by",
        "has_order_by",
        "has_union",
    ):
        if key in expect:
            actual = complexity.get(key, False)
            assert actual == expect[key], (
                f"Query {num} ({name}): expected {key}={expect[key]}, got {actual}"
            )

    if "join_count" in expect:
        actual = complexity.get("join_count", 0)
        assert actual == expect["join_count"], (
            f"Query {num} ({name}): expected join_count={expect['join_count']}, got {actual}"
        )


# ---- Test -------------------------------------------------------------------


class TestQueryAnalyzerExamples:
    """Run 10 example queries against postgres.accdb and generate a report."""

    @pytest.mark.com_integration
    def test_all_queries_and_generate_report(self, com_connection):
        """Execute all example queries, validate, and render docs report."""
        adapter = connection_service.get_adapter(CONNECTION_NAME)
        results: list[dict] = []

        for num, q in enumerate(QUERIES, 1):
            result = QueryAnalyzerService.analyze(
                sql=q["sql"],
                params=None,
                adapter=adapter,
                dry_run=False,
                sample_size=3,
            )

            # -- Structural assertions --
            assert result["success"] is True, (
                f"Query {num} ({q['name']}) failed: {result.get('error')}"
            )

            complexity = result.get("complexity", {})
            _check_complexity_expectation(num, q["name"], q["expect"], complexity)

            # Schema analysis
            schema = result.get("schema_analysis", {})
            assert schema.get("success") is True, (
                f"Query {num} ({q['name']}): schema analysis failed — {schema.get('error')}"
            )
            # COM adapter found the table(s) — index_info_available depends on
            # whether non-PK indexes exist. postgres.accdb only has autoindexed
            # PKs/FKs, which live in primary_key (not indexes), so the flag
            # may be False — and that's a valid result.
            assert schema.get("table_count", 0) >= 1, (
                f"Query {num} ({q['name']}): expected at least 1 table in schema"
            )

            # Execution timing (allow error for YEAR() query)
            execution = result.get("execution", {})
            if not execution.get("error"):
                assert execution.get("duration_ms") is not None and execution["duration_ms"] >= 0, (
                    f"Query {num} ({q['name']}): expected duration_ms >= 0"
                )

            # At least one recommendation
            assert len(result.get("recommendations", [])) > 0, (
                f"Query {num} ({q['name']}): expected at least one recommendation"
            )

            results.append(
                {
                    "num": num,
                    "name": q["name"],
                    "description": q["description"],
                    "sql": q["sql"],
                    "result": result,
                }
            )

        # Render report
        report_md = _render_report(results)
        DOCS_PATH.parent.mkdir(parents=True, exist_ok=True)
        DOCS_PATH.write_text(report_md, encoding="utf-8")
        print(f"  Report generated: {DOCS_PATH}")


# ---- Report renderer --------------------------------------------------------


def _render_report(results: list[dict]) -> str:
    """Render a Markdown report from all query results."""
    lines: list[str] = []
    _w = lines.append

    _w("# Query Analyzer — Live Examples on `postgres.accdb`")
    _w("")
    _w("**Generated:** 2026-06-05")
    _w("**Connection:** COM (WinComAdapter) — full schema index analysis")
    _w("**Mode:** `dry_run=false`, `sample_size=3`")
    _w("")
    _w("---")
    _w("")

    # ---- Summary table ----
    _w("## Summary")
    _w("")
    _w("| # | Query | Complexity | Score | Duration | Rows | Anti-patterns |")
    _w("|---|-------|------------|-------|----------|------|---------------|")
    for r in results:
        c: dict = r["result"]["complexity"]
        e: dict = r["result"]["execution"]
        dur = f"{e['duration_ms']:.1f}ms" if e.get("duration_ms") else "⚠️ error"
        rows_total = e.get("rows_total")
        rows_str = str(rows_total) if rows_total is not None else "⚠️ error"

        active: list[str] = []
        if c.get("join_count"):
            active.append(f"JOIN({c['join_count']})")
        if c.get("has_subquery"):
            active.append("SubQ")
        if c.get("has_leading_wildcard_like"):
            active.append("Wildcard")
        if c.get("has_where_function"):
            active.append("FuncWHERE")
        if c.get("has_cartesian_join"):
            active.append("Cartesian")
        if c.get("has_not_in"):
            active.append("NOT IN")
        if c.get("has_aggregates"):
            active.append("Agg")
        if c.get("has_group_by"):
            active.append("GROUP BY")
        if c.get("has_order_by"):
            active.append("ORDER BY")

        pattern_str = ", ".join(active) if active else "—"

        _w(
            f"| {r['num']} | {r['name'][:50]} | {c['complexity_label']} | "
            f"{c['score']} | {dur} | {rows_str} | {pattern_str} |"
        )

    _w("")
    _w("---")
    _w("")

    # ---- Detail sections ----
    for r in results:
        c = r["result"]["complexity"]
        e = r["result"]["execution"]
        s = r["result"]["schema_analysis"]
        recs = r["result"]["recommendations"]

        _w(f"## {r['num']}. {r['name']}")
        _w("")
        _w(f"*{r['description']}*")
        _w("")
        _w("```sql")
        _w(r["sql"])
        _w("```")
        _w("")

        # Complexity table
        _w("### Complexity")
        _w("")
        _w(f"**Label:** {c['complexity_label']}  |  **Score:** {c['score']}/100")
        _w("")
        _w("| Pattern | Detected |")
        _w("|---------|----------|")
        _w(f"| Joins | {'✓' if c['join_count'] else '✗'} ({c['join_count']}) |")
        _w(f"| Subquery | {'✓' if c['has_subquery'] else '✗'} |")
        _w(f"| Correlated subquery | {'✓' if c['has_correlated_subquery'] else '✗'} |")
        _w(f"| DISTINCT | {'✓' if c['has_distinct'] else '✗'} |")
        _w(f"| ORDER BY | {'✓' if c['has_order_by'] else '✗'} |")
        _w(f"| GROUP BY | {'✓' if c['has_group_by'] else '✗'} |")
        _w(f"| Aggregate functions | {'✓' if c['has_aggregates'] else '✗'} |")
        _w(f"| Function in WHERE | {'✓' if c['has_where_function'] else '✗'} |")
        _w(f"| Leading wildcard LIKE | {'✓' if c['has_leading_wildcard_like'] else '✗'} |")
        _w(f"| Cartesian join | {'✓' if c['has_cartesian_join'] else '✗'} |")
        _w(f"| NOT IN | {'✓' if c['has_not_in'] else '✗'} |")
        _w(f"| OR condition | {'✓' if c['has_or_condition'] else '✗'} |")
        _w(f"| UNION | {'✓' if c['has_union'] else '✗'} |")
        _w("")

        # Execution
        _w("### Execution")
        _w("")
        if e.get("error"):
            _w(f"⚠️ **Execution error:** {e['error']}")
            _w("")
        else:
            dur_str = f"{e['duration_ms']:.2f}ms" if e.get("duration_ms") is not None else "N/A"
            _w(f"**Duration:** {dur_str}")
            _w("")
            _w(f"**Rows (COUNT):** {e.get('rows_total') or 'N/A'}")
            _w("")
            if e.get("sampled_data"):
                _w("**Sample rows:**")
                _w("")
                _w("```json")
                _w(json.dumps(e["sampled_data"], indent=2, default=str))
                _w("```")
                _w("")

        # Schema
        _w("### Schema Analysis")
        _w("")
        _w(f"**Tables analyzed:** {s.get('table_count', 0)}")
        _w(f"**Index info available:** {'✓' if s.get('index_info_available') else '✗'}")
        indexed = s.get("indexed_columns", {})
        if indexed:
            _w("")
            _w("| Table | Indexed columns |")
            _w("|-------|-----------------|")
            for table, cols in sorted(indexed.items()):
                _w(f"| `{table}` | {', '.join(sorted(cols))} |")
        _w("")

        # Recommendations
        _w("### Recommendations")
        _w("")
        if recs:
            for rec in recs:
                _w(f"- {rec}")
        else:
            _w("*(none)*")
        _w("")

        # Full JSON
        _w("### Full Result")
        _w("")
        _w("<details>")
        _w("<summary>Click to expand JSON</summary>")
        _w("")
        _w("```json")
        _w(json.dumps(r["result"], indent=2, default=str))
        _w("```")
        _w("")
        _w("</details>")
        _w("")
        _w("---")
        _w("")

    return "\n".join(lines)
