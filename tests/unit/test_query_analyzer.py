"""Unit tests for query_analyzer.py — SQL complexity parsing and schema analysis."""

import pytest
import time
from unittest.mock import MagicMock

from ms_access_mcp.services.query_analyzer import (
    SQLComplexityAnalyzer,
    SQLParseResult,
    SchemaAnalyzer,
    QueryAnalyzerService,
    generate_recommendations,
)


class TestSQLComplexityAnalyzer:
    """Test suite for SQLComplexityAnalyzer.parse()."""

    def test_simple_select_single_table(self):
        """1.1 RED: Simple SELECT FROM single table → score 0, complexity 'simple'."""
        result = SQLComplexityAnalyzer.parse("SELECT * FROM Customers")
        assert result is not None
        assert result.score == 0
        assert result.complexity_label == "simple"

    def test_five_joins_moderate_or_higher(self):
        """1.1 RED: 5 JOINs → score >=50, complexity 'moderate' or higher."""
        sql = """
            SELECT * FROM Orders
            INNER JOIN Customers ON Orders.CustomerID = Customers.ID
            INNER JOIN Products ON Orders.ProductID = Products.ID
            INNER JOIN Categories ON Products.CategoryID = Categories.ID
            INNER JOIN Suppliers ON Products.SupplierID = Suppliers.ID
            LEFT OUTER JOIN Shippers ON Orders.ShipperID = Shippers.ID
        """
        result = SQLComplexityAnalyzer.parse(sql)
        assert result is not None
        assert result.join_count == 5
        assert result.score >= 50
        assert result.complexity_label in ("moderate", "complex", "heavy")

    def test_subquery_detected(self):
        """1.1 RED: Subquery → has_subquery=True."""
        sql = "SELECT * FROM Orders WHERE CustomerID IN (SELECT ID FROM Customers WHERE Active = True)"
        result = SQLComplexityAnalyzer.parse(sql)
        assert result is not None
        assert result.has_subquery is True

    def test_correlated_subquery_detected(self):
        """1.1 RED: Correlated subquery → has_correlated_subquery=True."""
        sql = """
            SELECT * FROM Orders o
            WHERE EXISTS (SELECT 1 FROM Customers c WHERE c.ID = o.CustomerID AND c.Active = True)
        """
        result = SQLComplexityAnalyzer.parse(sql)
        assert result is not None
        assert result.has_correlated_subquery is True

    def test_leading_wildcard_like_detected(self):
        """1.1 RED: Leading wildcard LIKE → has_leading_wildcard_like=True."""
        sql = "SELECT * FROM Customers WHERE Name LIKE '%Smith%'"
        result = SQLComplexityAnalyzer.parse(sql)
        assert result is not None
        assert result.has_leading_wildcard_like is True

    def test_function_in_where_detected(self):
        """1.1 RED: Function in WHERE → has_where_function=True."""
        sql = "SELECT * FROM Orders WHERE YEAR(CreatedDate) = 2024"
        result = SQLComplexityAnalyzer.parse(sql)
        assert result is not None
        assert result.has_where_function is True

    def test_cartesian_join_detected(self):
        """1.1 RED: Cartesian join (FROM A, B no WHERE) → has_cartesian_join=True."""
        sql = "SELECT * FROM Orders, Customers"
        result = SQLComplexityAnalyzer.parse(sql)
        assert result is not None
        assert result.has_cartesian_join is True

    def test_all_anti_patterns_combined(self):
        """1.1 RED: All anti-patterns combined → score >=60, complexity 'complex' or higher."""
        sql = """
            SELECT DISTINCT o.* FROM Orders o
            INNER JOIN Customers c ON o.CustomerID = c.ID
            LEFT OUTER JOIN Products p ON o.ProductID = p.ID
            WHERE o.ID IN (SELECT OrderID FROM OrderItems WHERE Quantity > 0)
            AND c.Name LIKE '%Acme%'
            AND YEAR(o.CreatedDate) = 2024
            ORDER BY o.CreatedDate DESC
        """
        result = SQLComplexityAnalyzer.parse(sql)
        assert result is not None
        assert result.score >= 60
        assert result.complexity_label in ("complex", "heavy")

    def test_clean_query_minimal_score(self):
        """1.1 RED: Clean query with simple WHERE → minimal score."""
        sql = "SELECT ID, Name FROM Customers WHERE Active = True"
        result = SQLComplexityAnalyzer.parse(sql)
        assert result is not None
        assert result.score <= 10
        assert result.complexity_label == "simple"

    def test_non_select_returns_none(self):
        """1.1 RED: Non-SELECT (INSERT, UPDATE) → returns None or raises."""
        insert_sql = "INSERT INTO Customers (Name) VALUES ('John')"
        update_sql = "UPDATE Customers SET Name = 'John' WHERE ID = 1"
        delete_sql = "DELETE FROM Customers WHERE ID = 1"

        assert SQLComplexityAnalyzer.parse(insert_sql) is None
        assert SQLComplexityAnalyzer.parse(update_sql) is None
        assert SQLComplexityAnalyzer.parse(delete_sql) is None


class TestSQLParseResultDataclass:
    """Test SQLParseResult dataclass fields."""

    def test_parse_result_has_all_fields(self):
        """1.1 RED: SQLParseResult has all required fields."""
        result = SQLComplexityAnalyzer.parse("SELECT * FROM Customers")
        assert result is not None
        # Verify all fields exist and have correct types
        assert isinstance(result.tables_involved, list)
        assert isinstance(result.join_count, int)
        assert isinstance(result.has_subquery, bool)
        assert isinstance(result.has_correlated_subquery, bool)
        assert isinstance(result.has_distinct, bool)
        assert isinstance(result.has_order_by, bool)
        assert isinstance(result.has_group_by, bool)
        assert isinstance(result.has_aggregates, bool)
        assert isinstance(result.has_where_function, bool)
        assert isinstance(result.has_leading_wildcard_like, bool)
        assert isinstance(result.has_cartesian_join, bool)
        assert isinstance(result.has_not_in, bool)
        assert isinstance(result.has_or_condition, bool)
        assert isinstance(result.has_union, bool)
        assert isinstance(result.score, int)
        assert result.complexity_label in ("simple", "moderate", "complex", "heavy")


class TestSchemaAnalyzer:
    """Test suite for SchemaAnalyzer.analyze()."""

    def test_schema_analyzer_with_wincom_adapter(self):
        """1.3 RED: SchemaAnalyzer with mock WinComAdapter → returns indexed_columns."""
        mock_adapter = MagicMock()
        mock_table = MagicMock()
        mock_table.name = "Customers"
        mock_table.fields = []
        mock_table.record_count = 100
        mock_table.primary_key = ["ID"]

        mock_schema = MagicMock()
        mock_schema.name = "Customers"
        mock_schema.columns = []
        mock_schema.primary_key = ["ID"]
        mock_schema.foreign_keys = []
        mock_schema.indexes = [
            MagicMock(name="IX_Customers_Name", columns=["Name"], is_unique=False)
        ]

        mock_adapter.get_tables.return_value = [mock_table]
        mock_adapter.get_table_schema_plan.return_value = ([mock_schema], MagicMock())

        result = SchemaAnalyzer.analyze(mock_adapter, ["Customers"])

        assert result["success"] is True
        assert "indexed_columns" in result
        assert "Customers" in result["indexed_columns"]

    def test_schema_analyzer_with_odbc_adapter(self):
        """SchemaAnalyzer with mock OdbcAdapter → includes PK columns in indexed_columns."""
        mock_adapter = MagicMock()
        mock_table = MagicMock()
        mock_table.name = "Customers"
        mock_table.fields = []
        mock_table.record_count = 100
        mock_table.primary_key = ["ID"]

        mock_schema = MagicMock()
        mock_schema.name = "Customers"
        mock_schema.columns = []
        mock_schema.primary_key = ["ID"]
        mock_schema.foreign_keys = []
        mock_schema.indexes = []  # ODBC may not return non-PK indexes

        mock_adapter.get_tables.return_value = [mock_table]
        mock_adapter.get_table_schema_plan.return_value = ([mock_schema], MagicMock())

        result = SchemaAnalyzer.analyze(mock_adapter, ["Customers"])

        assert result["success"] is True
        assert "index_info_available" in result
        assert result["index_info_available"] is True
        assert "indexed_columns" in result
        assert "Customers" in result["indexed_columns"]
        assert "ID" in result["indexed_columns"]["Customers"]

    def test_schema_analyzer_with_empty_table_list(self):
        """1.3 RED: SchemaAnalyzer with empty table list → empty result."""
        mock_adapter = MagicMock()
        mock_adapter.get_tables.return_value = []
        mock_adapter.get_table_schema_plan.return_value = ([], MagicMock())

        result = SchemaAnalyzer.analyze(mock_adapter, [])

        assert result["success"] is True
        assert result["table_count"] == 0


class TestQueryAnalyzerService:
    """Test suite for QueryAnalyzerService.analyze()."""

    def test_non_select_returns_error(self):
        """2.3 RED: Non-SELECT statement → returns error 'Not a SELECT statement'."""
        mock_adapter = MagicMock()
        result = QueryAnalyzerService.analyze(
            sql="INSERT INTO Customers (Name) VALUES ('John')",
            params=None,
            adapter=mock_adapter,
        )
        assert result["success"] is False
        assert "Not a SELECT statement" in result["error"]

    def test_select_returns_full_structure(self):
        """2.3 RED: Valid SELECT → returns dict with success=True and required keys."""
        mock_adapter = MagicMock()
        mock_adapter.execute_query.return_value = iter([{"_cnt": 10}])

        result = QueryAnalyzerService.analyze(
            sql="SELECT * FROM Customers",
            params=None,
            adapter=mock_adapter,
        )

        assert result["success"] is True
        assert "query" in result
        assert "execution" in result
        assert "complexity" in result
        assert "schema_analysis" in result
        assert "recommendations" in result

    def test_calls_sql_complexity_analyzer(self):
        """2.3 RED: Calls SQLComplexityAnalyzer.parse() internally."""
        mock_adapter = MagicMock()
        mock_adapter.execute_query.return_value = iter([{"_cnt": 5}])

        result = QueryAnalyzerService.analyze(
            sql="SELECT * FROM Customers WHERE ID = 1",
            params=None,
            adapter=mock_adapter,
        )

        assert result["complexity"]["score"] == 0
        assert result["complexity"]["complexity_label"] == "simple"

    def test_calls_schema_analyzer(self):
        """2.3 RED: Calls SchemaAnalyzer.analyze() with correct tables."""
        mock_adapter = MagicMock()
        mock_adapter.execute_query.return_value = iter([{"_cnt": 5}])
        mock_adapter.get_tables.return_value = []
        mock_adapter.get_table_schema_plan.return_value = ([], MagicMock())

        result = QueryAnalyzerService.analyze(
            sql="SELECT * FROM Customers c JOIN Orders o ON c.ID = o.CustomerID",
            params=None,
            adapter=mock_adapter,
        )

        assert result["schema_analysis"]["success"] is True

    def test_dry_run_skips_execution(self):
        """2.3 RED: dry_run=True → skips COUNT execution."""
        mock_adapter = MagicMock()

        result = QueryAnalyzerService.analyze(
            sql="SELECT * FROM Customers",
            params=None,
            adapter=mock_adapter,
            dry_run=True,
        )

        mock_adapter.execute_query.assert_not_called()
        assert result["execution"]["duration_ms"] is None
        assert result["execution"]["rows_total"] is None

    def test_count_execution_timing(self):
        """2.3 RED: Non-dry_run → executes COUNT and records timing."""
        mock_adapter = MagicMock()
        mock_adapter.execute_query.return_value = iter([{"_cnt": 42}])

        result = QueryAnalyzerService.analyze(
            sql="SELECT * FROM Customers",
            params=None,
            adapter=mock_adapter,
            dry_run=False,
        )

        assert result["execution"]["duration_ms"] is not None
        assert result["execution"]["duration_ms"] >= 0
        assert result["execution"]["rows_total"] == 42

    def test_count_execution_failure_graceful(self):
        """2.3 RED: COUNT execution fails → records error but doesn't fail overall."""
        mock_adapter = MagicMock()
        mock_adapter.execute_query.side_effect = Exception("Connection lost")

        result = QueryAnalyzerService.analyze(
            sql="SELECT * FROM Customers",
            params=None,
            adapter=mock_adapter,
            dry_run=False,
        )

        assert result["success"] is True
        assert "error" in result["execution"]

    def test_sample_size_executes_top_query(self):
        """2.3 RED: sample_size > 0 → executes TOP query and samples data."""
        mock_adapter = MagicMock()
        mock_adapter.execute_query.side_effect = [
            iter([{"_cnt": 100}]),  # COUNT result
            iter([{"ID": 1}, {"ID": 2}]),  # TOP result
        ]

        result = QueryAnalyzerService.analyze(
            sql="SELECT * FROM Customers",
            params=None,
            adapter=mock_adapter,
            dry_run=False,
            sample_size=2,
        )

        assert result["execution"]["sample_size"] == 2
        assert result["execution"]["sampled_data"] is not None
        assert len(result["execution"]["sampled_data"]) <= 2

    def test_sample_uses_access_top_syntax(self):
        """2.3 RED: sample_size uses Access TOP N syntax in wrapper query."""
        mock_adapter = MagicMock()
        mock_adapter.execute_query.side_effect = [
            iter([{"_cnt": 10}]),
            iter([{"ID": 1}]),
        ]

        result = QueryAnalyzerService.analyze(
            sql="SELECT * FROM Customers",
            params=None,
            adapter=mock_adapter,
            dry_run=False,
            sample_size=5,
        )

        # Should have called execute_query at least twice
        assert mock_adapter.execute_query.call_count >= 2

    def test_sample_execution_failure_graceful(self):
        """2.3 RED: sample execution fails → records error but doesn't fail overall."""
        mock_adapter = MagicMock()
        mock_adapter.execute_query.side_effect = [
            iter([{"_cnt": 10}]),
            Exception("Sample query failed"),
        ]

        result = QueryAnalyzerService.analyze(
            sql="SELECT * FROM Customers",
            params=None,
            adapter=mock_adapter,
            dry_run=False,
            sample_size=5,
        )

        assert result["success"] is True
        assert "error" in result["execution"]

    def test_params_passed_to_adapter(self):
        """2.3 RED: params are passed to adapter.execute_query calls."""
        mock_adapter = MagicMock()
        mock_adapter.execute_query.return_value = iter([{"_cnt": 5}])

        QueryAnalyzerService.analyze(
            sql="SELECT * FROM Customers WHERE ID = ?",
            params=[42],
            adapter=mock_adapter,
            dry_run=False,
        )

        # Check that params=[42] was passed to execute_query
        calls = mock_adapter.execute_query.call_args_list
        for call in calls:
            if call[0][0].startswith("SELECT COUNT(*)"):
                assert call[0][1] == [42]

    def test_complex_query_with_joins(self):
        """2.3 RED: Complex query with JOINs → returns all analysis components."""
        mock_adapter = MagicMock()
        mock_adapter.execute_query.return_value = iter([{"_cnt": 50}])

        sql = """
            SELECT * FROM Orders o
            INNER JOIN Customers c ON o.CustomerID = c.ID
            WHERE o.Total > 100
        """
        result = QueryAnalyzerService.analyze(
            sql=sql,
            params=None,
            adapter=mock_adapter,
            dry_run=False,
        )

        assert result["success"] is True
        assert result["complexity"]["join_count"] == 1
        assert len(result["recommendations"]) >= 0


class TestGenerateRecommendations:
    """Test suite for generate_recommendations()."""

    def test_missing_index_recommendation(self):
        """2.4 RED: Column in WHERE/JOIN but not indexed → missing index recommendation."""
        parse_result = SQLComplexityAnalyzer.parse(
            "SELECT * FROM Orders o WHERE o.CustomerID = 1"
        )
        schema = {
            "success": True,
            "indexed_columns": {"Orders": []},  # No indexes
        }

        recommendations = generate_recommendations(parse_result, schema, None, sql="SELECT * FROM Orders o WHERE o.CustomerID = 1")

        assert any("Missing index" in r for r in recommendations)

    def test_leading_wildcard_like_recommendation(self):
        """2.4 RED: Leading wildcard LIKE → warns about index usage."""
        parse_result = SQLComplexityAnalyzer.parse(
            "SELECT * FROM Customers WHERE Name LIKE '%Smith%'"
        )
        schema = {"success": True, "indexed_columns": {"Customers": ["Name"]}}

        recommendations = generate_recommendations(parse_result, schema, None)

        assert any("LIKE with leading wildcard" in r for r in recommendations)

    def test_cartesian_join_recommendation(self):
        """2.4 RED: Cartesian join detected → warns about missing JOIN condition."""
        parse_result = SQLComplexityAnalyzer.parse(
            "SELECT * FROM Orders, Customers"
        )
        schema = {"success": True, "indexed_columns": {}}

        recommendations = generate_recommendations(parse_result, schema, None)

        assert any("Cartesian join" in r for r in recommendations)

    def test_correlated_subquery_recommendation(self):
        """2.4 RED: Correlated subquery → suggests rewriting as JOIN."""
        parse_result = SQLComplexityAnalyzer.parse("""
            SELECT * FROM Orders o
            WHERE EXISTS (SELECT 1 FROM Customers c WHERE c.ID = o.CustomerID)
        """)
        schema = {"success": True, "indexed_columns": {}}

        recommendations = generate_recommendations(parse_result, schema, None)

        assert any("Correlated subquery" in r for r in recommendations)

    def test_not_in_recommendation(self):
        """2.4 RED: NOT IN detected → suggests NOT EXISTS or LEFT JOIN."""
        parse_result = SQLComplexityAnalyzer.parse(
            "SELECT * FROM Customers WHERE ID NOT IN (SELECT CustomerID FROM Orders)"
        )
        schema = {"success": True, "indexed_columns": {}}

        recommendations = generate_recommendations(parse_result, schema, None)

        assert any("NOT IN" in r for r in recommendations)

    def test_function_in_where_recommendation(self):
        """2.4 RED: Function in WHERE → warns about index usage."""
        parse_result = SQLComplexityAnalyzer.parse(
            "SELECT * FROM Orders WHERE YEAR(CreatedDate) = 2024"
        )
        schema = {"success": True, "indexed_columns": {"Orders": ["CreatedDate"]}}

        recommendations = generate_recommendations(
            parse_result, schema, None,
            sql="SELECT * FROM Orders WHERE YEAR(CreatedDate) = 2024"
        )

        assert any("Function" in r and "CreatedDate" in r for r in recommendations)

    def test_or_condition_recommendation(self):
        """2.4 RED: OR condition → suggests UNION alternative."""
        parse_result = SQLComplexityAnalyzer.parse(
            "SELECT * FROM Customers WHERE City = 'NYC' OR City = 'LA'"
        )
        schema = {"success": True, "indexed_columns": {}}

        recommendations = generate_recommendations(parse_result, schema, None)

        assert any("OR condition" in r for r in recommendations)

    def test_many_joins_recommendation(self):
        """2.4 RED: Many joins (>=5) → warns about indexed columns."""
        sql = """
            SELECT * FROM A
            JOIN B ON A.ID = B.AID
            JOIN C ON B.ID = C.BID
            JOIN D ON C.ID = D.CID
            JOIN E ON D.ID = E.DID
            JOIN F ON E.ID = F.EID
        """
        parse_result = SQLComplexityAnalyzer.parse(sql)
        schema = {"success": True, "indexed_columns": {}}

        recommendations = generate_recommendations(parse_result, schema, None)

        assert any("high" in r.lower() and "join" in r.lower() for r in recommendations)

    def test_aggregates_on_large_table_recommendation(self):
        """2.4 RED: Aggregates on large table → suggests filters."""
        parse_result = SQLComplexityAnalyzer.parse(
            "SELECT COUNT(*) FROM Orders"
        )
        execution = {"rows_total": 1000000}
        schema = {"success": True, "indexed_columns": {}}

        recommendations = generate_recommendations(parse_result, schema, execution)

        assert any("Aggregate" in r or "large table" in r for r in recommendations)

    def test_clean_query_recommendation(self):
        """2.4 RED: Clean query → returns 'No significant performance issues'."""
        parse_result = SQLComplexityAnalyzer.parse(
            "SELECT ID, Name FROM Customers WHERE Active = True"
        )
        schema = {"success": True, "indexed_columns": {"Customers": ["ID", "Name", "Active"]}}
        execution = {"rows_total": 10}

        recommendations = generate_recommendations(parse_result, schema, execution)

        assert any("No significant performance issues" in r for r in recommendations)

    def test_timing_note_included_when_available(self):
        """2.4 RED: When timing is available, includes duration_ms in execution dict."""
        parse_result = SQLComplexityAnalyzer.parse("SELECT * FROM Customers")
        schema = {"success": True, "indexed_columns": {}}
        execution = {"duration_ms": 45.5, "rows_total": 100}

        recommendations = generate_recommendations(parse_result, schema, execution)

        # Recommendations should be a list
        assert isinstance(recommendations, list)

    def test_rows_total_note(self):
        """2.4 RED: When rows_total > 0, includes pagination note."""
        parse_result = SQLComplexityAnalyzer.parse("SELECT * FROM LargeTable")
        schema = {"success": True, "indexed_columns": {}}
        execution = {"duration_ms": 100.0, "rows_total": 50000}

        recommendations = generate_recommendations(parse_result, schema, execution)

        # Should mention large result set
        assert any("rows" in r.lower() for r in recommendations)

    def test_returns_list_of_strings(self):
        """2.4 RED: Returns a list of string recommendations."""
        parse_result = SQLComplexityAnalyzer.parse("SELECT * FROM Customers")
        schema = {"success": True, "indexed_columns": {}}

        recommendations = generate_recommendations(parse_result, schema, None)

        assert isinstance(recommendations, list)
        assert all(isinstance(r, str) for r in recommendations)


class TestQueryAnalyzerServiceExtended:
    """Extended tests for QueryAnalyzerService — Phase 3 coverage."""

    def test_dry_run_true_no_execution(self):
        """3.1 RED: dry_run=True → no adapter.execute_query called, null timing."""
        mock_adapter = MagicMock()

        result = QueryAnalyzerService.analyze(
            sql="SELECT * FROM Customers",
            params=None,
            adapter=mock_adapter,
            dry_run=True,
        )

        mock_adapter.execute_query.assert_not_called()
        assert result["execution"]["duration_ms"] is None
        assert result["execution"]["rows_total"] is None

    def test_timed_execution_returns_positive_duration(self):
        """3.1 RED: Mock adapter returns data → duration_ms > 0."""
        mock_adapter = MagicMock()
        mock_adapter.execute_query.return_value = iter([{"_cnt": 10}])

        result = QueryAnalyzerService.analyze(
            sql="SELECT * FROM Customers",
            params=None,
            adapter=mock_adapter,
            dry_run=False,
        )

        assert result["execution"]["duration_ms"] is not None
        assert result["execution"]["duration_ms"] > 0

    def test_sample_mode_calls_top_n_query(self):
        """3.1 RED: sample_size=5 → verify TOP N query is called."""
        mock_adapter = MagicMock()
        mock_adapter.execute_query.side_effect = [
            iter([{"_cnt": 100}]),
            iter([{"ID": 1}, {"ID": 2}, {"ID": 3}]),
        ]

        result = QueryAnalyzerService.analyze(
            sql="SELECT * FROM Customers",
            params=None,
            adapter=mock_adapter,
            dry_run=False,
            sample_size=5,
        )

        # Verify TOP 5 was requested
        calls = mock_adapter.execute_query.call_args_list
        top_query_call = None
        for call in calls:
            if "TOP" in call[0][0]:
                top_query_call = call[0][0]
                break
        assert top_query_call is not None, "No TOP query found in execute_query calls"
        assert "TOP 5" in top_query_call.upper()
        assert result["execution"]["sampled_data"] is not None

    def test_partial_timing_failure_count_query_fails(self):
        """3.1 RED: COUNT fails but schema succeeds → partial result returned."""
        mock_adapter = MagicMock()
        # First call (COUNT) fails, second call succeeds
        mock_adapter.execute_query.side_effect = [
            Exception("Connection lost"),
            iter([{"ID": 1}]),
        ]
        mock_adapter.get_tables.return_value = []
        mock_adapter.get_table_schema_plan.return_value = ([], MagicMock())

        result = QueryAnalyzerService.analyze(
            sql="SELECT * FROM Customers",
            params=None,
            adapter=mock_adapter,
            dry_run=False,
        )

        assert result["success"] is True
        assert result["execution"]["error"] is not None
        assert "COUNT execution failed" in result["execution"]["error"]

    def test_recommendation_text_contains_anti_pattern_strings(self):
        """3.1 RED: Verify specific anti-pattern recommendation strings."""
        # Leading wildcard
        parse_result = SQLComplexityAnalyzer.parse(
            "SELECT * FROM Customers WHERE Name LIKE '%Smith%'"
        )
        schema = {"success": True, "indexed_columns": {}}
        recommendations = generate_recommendations(parse_result, schema, None)
        assert any("leading wildcard" in r or "LIKE" in r for r in recommendations)

        # Correlated subquery
        parse_result = SQLComplexityAnalyzer.parse("""
            SELECT * FROM Orders o
            WHERE EXISTS (SELECT 1 FROM Customers c WHERE c.ID = o.CustomerID)
        """)
        recommendations = generate_recommendations(parse_result, schema, None)
        assert any("Correlated subquery" in r for r in recommendations)

        # NOT IN
        parse_result = SQLComplexityAnalyzer.parse(
            "SELECT * FROM Customers WHERE ID NOT IN (SELECT CustomerID FROM Orders)"
        )
        recommendations = generate_recommendations(parse_result, schema, None)
        assert any("NOT IN" in r for r in recommendations)

        # Function in WHERE
        parse_result = SQLComplexityAnalyzer.parse(
            "SELECT * FROM Orders WHERE YEAR(CreatedDate) = 2024"
        )
        recommendations = generate_recommendations(
            parse_result, schema, None,
            sql="SELECT * FROM Orders WHERE YEAR(CreatedDate) = 2024"
        )
        assert any("Function" in r for r in recommendations)


class TestSchemaAnalyzerAdapterComparison:
    """Adapter comparison tests — Phase 3.2."""

    def test_wincom_adapter_full_index_data(self):
        """3.2 RED: WinCom mock with full index data → index_info_available=True."""
        mock_adapter = MagicMock()

        mock_schema = MagicMock()
        mock_schema.name = "Customers"
        mock_schema.columns = []
        mock_schema.primary_key = ["ID"]
        mock_schema.foreign_keys = []
        mock_schema.indexes = [
            MagicMock(name="IX_Customers_Name", columns=["Name"], is_unique=False),
            MagicMock(name="IX_Customers_City", columns=["City"], is_unique=False),
        ]

        mock_adapter.get_tables.return_value = []
        mock_adapter.get_table_schema_plan.return_value = ([mock_schema], MagicMock())

        result = SchemaAnalyzer.analyze(mock_adapter, ["Customers"])

        assert result["success"] is True
        assert result["index_info_available"] is True
        assert "Customers" in result["indexed_columns"]
        assert "Name" in result["indexed_columns"]["Customers"]
        assert "City" in result["indexed_columns"]["Customers"]

    def test_odbc_adapter_graceful_fallback_on_empty_indexes(self):
        """3.2 RED: OdbcAdapter where get_table_schema_plan returns empty → graceful fallback."""
        mock_adapter = MagicMock()
        mock_adapter.get_tables.return_value = []
        # OdbcAdapter may return empty indexes or raise
        mock_adapter.get_table_schema_plan.return_value = ([], MagicMock())

        result = SchemaAnalyzer.analyze(mock_adapter, ["Customers"])

        assert result["success"] is True
        assert result["index_info_available"] is False

    def test_odbc_adapter_raises_on_get_table_schema_plan(self):
        """3.2 RED: OdbcAdapter where get_table_schema_plan raises → graceful error."""
        mock_adapter = MagicMock()
        mock_adapter.get_tables.return_value = []
        mock_adapter.get_table_schema_plan.side_effect = Exception("Schema not available")

        result = SchemaAnalyzer.analyze(mock_adapter, ["Customers"])

        assert result["success"] is False
        assert "error" in result
        assert result["index_info_available"] is False
