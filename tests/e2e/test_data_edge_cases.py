"""
E2E data edge case tests — round-trip validation for Unicode, special chars,
long text, numeric boundaries, booleans, and special identifiers.

All tests use __e2e_edge_ prefix for created objects.
Cleanup: explicit try/finally blocks (not autouse fixtures).
Uses e2e_pool fixture (SQLite-backed adapter).
"""

import pytest

from tests.e2e.conftest import e2e_pool, call_mcp_tool
from tests.e2e.helpers import assert_workflow_result


# ============================================================================
# Phase 2: Unicode & Special Characters
# ============================================================================

class TestUnicodeRoundTrip:
    """Round-trip Unicode strings through create_table → insert_data → query_data.

    Covers: emoji, accented chars, CJK, Cyrillic.
    """

    @staticmethod
    def _text_columns() -> list[dict]:
        return [{"name": "id", "type": "Long Integer"}, {"name": "data", "type": "Text", "size": 500}]

    def test_emoji_and_accented_chars(self, e2e_pool):
        """Emoji and accented characters survive insert→query unmodified."""
        TABLE = "__e2e_edge_unicode1"
        pool = e2e_pool

        try:
            call_mcp_tool("create_table", TABLE, self._text_columns(), connection_service=pool)
            test_rows = [
                {"id": 1, "data": "🔥 Fire emoji"},
                {"id": 2, "data": "MëtällïcBóx"},
                {"id": 3, "data": "café naïve"},
            ]
            result = call_mcp_tool("insert_data", TABLE, test_rows, connection_service=pool)
            assert_workflow_result(result, expected_success=True)

            query = call_mcp_tool(
                "query_data",
                "SELECT id, data FROM " + TABLE + " ORDER BY id",
                connection_service=pool,
            )
            assert_workflow_result(query, expected_success=True)
            rows = query.get("rows", [])
            assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}"
            assert rows[0]["data"] == "🔥 Fire emoji"
            assert rows[1]["data"] == "MëtällïcBóx"
            assert rows[2]["data"] == "café naïve"

        finally:
            if pool.is_connected("default"):
                adapter = pool.get_adapter("default")
                try:
                    adapter.execute_query(f"DROP TABLE IF EXISTS [{TABLE}]")
                except Exception:
                    pass

    def test_cjk_and_cyrillic(self, e2e_pool):
        """CJK and Cyrillic characters survive insert→query unmodified."""
        TABLE = "__e2e_edge_unicode2"
        pool = e2e_pool

        try:
            call_mcp_tool("create_table", TABLE, self._text_columns(), connection_service=pool)
            test_rows = [
                {"id": 1, "data": "日本語"},
                {"id": 2, "data": "こんにちは世界"},
                {"id": 3, "data": "привет"},
                {"id": 4, "data": "Здравствуйте"},
            ]
            result = call_mcp_tool("insert_data", TABLE, test_rows, connection_service=pool)
            assert_workflow_result(result, expected_success=True)

            query = call_mcp_tool(
                "query_data",
                "SELECT id, data FROM " + TABLE + " ORDER BY id",
                connection_service=pool,
            )
            assert_workflow_result(query, expected_success=True)
            rows = query.get("rows", [])
            assert len(rows) == 4, f"Expected 4 rows, got {len(rows)}"
            assert rows[0]["data"] == "日本語"
            assert rows[1]["data"] == "こんにちは世界"
            assert rows[2]["data"] == "привет"
            assert rows[3]["data"] == "Здравствуйте"

        finally:
            if pool.is_connected("default"):
                adapter = pool.get_adapter("default")
                try:
                    adapter.execute_query(f"DROP TABLE IF EXISTS [{TABLE}]")
                except Exception:
                    pass


class TestSpecialCharactersData:
    """Round-trip SQL-significant characters: quotes, tabs, newlines, commas."""

    @staticmethod
    def _text_columns() -> list[dict]:
        return [{"name": "id", "type": "Long Integer"}, {"name": "data", "type": "Text", "size": 500}]

    def test_quotes_tabs_newlines_commas(self, e2e_pool):
        """Single quotes, double quotes, tabs, newlines, and commas survive unmodified."""
        TABLE = "__e2e_edge_special"
        pool = e2e_pool

        try:
            call_mcp_tool("create_table", TABLE, self._text_columns(), connection_service=pool)
            test_rows = [
                {"id": 1, "data": "O'Brien"},
                {"id": 2, "data": 'She said "hello"'},
                {"id": 3, "data": "field1\tfield2"},
                {"id": 4, "data": "line1\nline2"},
                {"id": 5, "data": "apple, banana, cherry"},
            ]
            result = call_mcp_tool("insert_data", TABLE, test_rows, connection_service=pool)
            assert_workflow_result(result, expected_success=True)

            query = call_mcp_tool(
                "query_data",
                "SELECT id, data FROM " + TABLE + " ORDER BY id",
                connection_service=pool,
            )
            assert_workflow_result(query, expected_success=True)
            rows = query.get("rows", [])
            assert len(rows) == 5, f"Expected 5 rows, got {len(rows)}"
            assert rows[0]["data"] == "O'Brien"
            assert rows[1]["data"] == 'She said "hello"'
            assert rows[2]["data"] == "field1\tfield2"
            assert rows[3]["data"] == "line1\nline2"
            assert rows[4]["data"] == "apple, banana, cherry"

        finally:
            if pool.is_connected("default"):
                adapter = pool.get_adapter("default")
                try:
                    adapter.execute_query(f"DROP TABLE IF EXISTS [{TABLE}]")
                except Exception:
                    pass


# ============================================================================
# Phase 3: Data Types
# ============================================================================

class TestMemoLongText:
    """Memo (long text) fields store and retrieve strings > 255 chars."""

    def test_memo_500_chars(self, e2e_pool):
        """500-character string survives round-trip via Memo column."""
        TABLE = "__e2e_edge_memo"
        pool = e2e_pool

        try:
            columns = [
                {"name": "id", "type": "Long Integer"},
                {"name": "memo", "type": "Memo"},
            ]
            call_mcp_tool("create_table", TABLE, columns, connection_service=pool)

            long_text = "A" * 500
            result = call_mcp_tool(
                "insert_data",
                TABLE,
                [{"id": 1, "memo": long_text}],
                connection_service=pool,
            )
            assert_workflow_result(result, expected_success=True)

            query = call_mcp_tool(
                "query_data",
                "SELECT id, memo FROM " + TABLE,
                connection_service=pool,
            )
            assert_workflow_result(query, expected_success=True)
            rows = query.get("rows", [])
            assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
            returned = rows[0]["memo"]
            assert returned == long_text, (
                f"Memo content mismatch: expected length {len(long_text)}, "
                f"got length {len(returned)}, content: {returned[:50]!r}..."
            )

        finally:
            if pool.is_connected("default"):
                adapter = pool.get_adapter("default")
                try:
                    adapter.execute_query(f"DROP TABLE IF EXISTS [{TABLE}]")
                except Exception:
                    pass


class TestNumericEdgeCases:
    """Numeric extremes: max int, negative, zero, high-precision decimals."""

    @staticmethod
    def _numeric_columns() -> list[dict]:
        return [
            {"name": "id", "type": "Long Integer"},
            {"name": "double_val", "type": "Double"},
            {"name": "currency_val", "type": "Currency"},
            {"name": "int_val", "type": "Integer"},
        ]

    def test_boundary_numbers(self, e2e_pool):
        """Max int, negative, zero, and decimal values round-trip exactly."""
        TABLE = "__e2e_edge_numeric"
        pool = e2e_pool

        try:
            call_mcp_tool("create_table", TABLE, self._numeric_columns(), connection_service=pool)

            test_rows = [
                {"id": 1, "double_val": 3.14159265, "currency_val": 999999.99, "int_val": 2147483647},
                {"id": 2, "double_val": -999999.99, "currency_val": -123.45, "int_val": -2147483648},
                {"id": 3, "double_val": 0.0, "currency_val": 0.0, "int_val": 0},
            ]
            result = call_mcp_tool("insert_data", TABLE, test_rows, connection_service=pool)
            assert_workflow_result(result, expected_success=True)

            query = call_mcp_tool(
                "query_data",
                "SELECT id, double_val, currency_val, int_val FROM " + TABLE + " ORDER BY id",
                connection_service=pool,
            )
            assert_workflow_result(query, expected_success=True)
            rows = query.get("rows", [])
            assert len(rows) == 3, f"Expected 3 rows, got {len(rows)}"

            # Row 1: max values — use tolerance for floats (SQLite stores as REAL)
            r1 = rows[0]
            assert r1["int_val"] == 2147483647, f"Expected max int, got {r1['int_val']}"
            assert abs(r1["double_val"] - 3.14159265) < 1e-6, f"Expected pi, got {r1['double_val']}"
            assert abs(r1["currency_val"] - 999999.99) < 0.01, f"Expected 999999.99, got {r1['currency_val']}"

            # Row 2: negative values
            r2 = rows[1]
            assert r2["int_val"] == -2147483648, f"Expected min int, got {r2['int_val']}"
            assert abs(r2["double_val"] - (-999999.99)) < 0.01, f"Expected -999999.99, got {r2['double_val']}"
            assert abs(r2["currency_val"] - (-123.45)) < 0.01, f"Expected -123.45, got {r2['currency_val']}"

            # Row 3: zero
            r3 = rows[2]
            assert r3["int_val"] == 0
            assert r3["double_val"] == 0.0
            assert r3["currency_val"] == 0.0

        finally:
            if pool.is_connected("default"):
                adapter = pool.get_adapter("default")
                try:
                    adapter.execute_query(f"DROP TABLE IF EXISTS [{TABLE}]")
                except Exception:
                    pass


class TestBooleanHandling:
    """Boolean True and False values round-trip correctly via Integer/Text."""

    def test_boolean_true_false(self, e2e_pool):
        """True and False survive insert→query as integers (SQLite has no BOOLEAN)."""
        TABLE = "__e2e_edge_bool"
        pool = e2e_pool

        try:
            columns = [
                {"name": "id", "type": "Long Integer"},
                {"name": "flag", "type": "Integer"},
            ]
            call_mcp_tool("create_table", TABLE, columns, connection_service=pool)

            test_rows = [{"id": 1, "flag": 1}, {"id": 2, "flag": 0}]
            result = call_mcp_tool("insert_data", TABLE, test_rows, connection_service=pool)
            assert_workflow_result(result, expected_success=True)

            query = call_mcp_tool(
                "query_data",
                "SELECT id, flag FROM " + TABLE + " ORDER BY id",
                connection_service=pool,
            )
            assert_workflow_result(query, expected_success=True)
            rows = query.get("rows", [])
            assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"
            assert rows[0]["flag"] == 1, f"Expected True (1), got {rows[0]['flag']}"
            assert rows[1]["flag"] == 0, f"Expected False (0), got {rows[1]['flag']}"

        finally:
            if pool.is_connected("default"):
                adapter = pool.get_adapter("default")
                try:
                    adapter.execute_query(f"DROP TABLE IF EXISTS [{TABLE}]")
                except Exception:
                    pass


# ============================================================================
# Phase 4: Identifiers
# ============================================================================

class TestSpecialIdentifiers:
    """Table names with spaces and underscores succeed via SQLite bracket quoting."""

    def test_table_name_with_spaces(self, e2e_pool):
        """Table name with spaces succeeds: create_table → insert_data → query_data."""
        TABLE = "__e2e_edge_table with spaces"
        pool = e2e_pool

        try:
            columns = [{"name": "id", "type": "Long Integer"}, {"name": "name", "type": "Text", "size": 50}]
            result = call_mcp_tool("create_table", TABLE, columns, connection_service=pool)
            assert_workflow_result(result, expected_success=True)

            insert_result = call_mcp_tool(
                "insert_data",
                TABLE,
                [{"id": 1, "name": "test row"}],
                connection_service=pool,
            )
            assert_workflow_result(insert_result, expected_success=True)

            query_result = call_mcp_tool(
                "query_data",
                'SELECT id, name FROM "' + TABLE + '"',
                connection_service=pool,
            )
            assert_workflow_result(query_result, expected_success=True)
            rows = query_result.get("rows", [])
            assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
            assert rows[0]["name"] == "test row"

        finally:
            if pool.is_connected("default"):
                adapter = pool.get_adapter("default")
                try:
                    adapter.execute_query(f"DROP TABLE IF EXISTS [{TABLE}]")
                except Exception:
                    pass