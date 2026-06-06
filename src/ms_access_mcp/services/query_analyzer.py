"""SQL complexity parsing and schema analysis services."""

import re
import time
from dataclasses import dataclass
from typing import Literal

# Scoring constants
SIMPLE_THRESHOLD = 20
MODERATE_THRESHOLD = 50
COMPLEX_THRESHOLD = 75

WEIGHT_JOIN = 10
WEIGHT_SUBQUERY = 15
WEIGHT_CORRELATED = 5
WEIGHT_LEADING_WILDCARD = 10
WEIGHT_FUNCTION_IN_WHERE = 8
WEIGHT_CARTESIAN = 15
WEIGHT_DISTINCT = 5
WEIGHT_ORDER_BY = 3
WEIGHT_GROUP_BY = 5
WEIGHT_NOT_IN = 8
WEIGHT_OR = 4
WEIGHT_UNION = 4
WEIGHT_AGGREGATE = 3


@dataclass
class SQLParseResult:
    """Result of SQL complexity analysis."""

    tables_involved: list[str]
    join_count: int
    has_subquery: bool
    has_correlated_subquery: bool
    has_distinct: bool
    has_order_by: bool
    has_group_by: bool
    has_aggregates: bool
    has_where_function: bool
    has_leading_wildcard_like: bool
    has_cartesian_join: bool
    has_not_in: bool
    has_or_condition: bool
    has_union: bool
    score: int
    complexity_label: Literal["simple", "moderate", "complex", "heavy"]


class SQLComplexityAnalyzer:
    """Static analyzer for SQL query complexity."""

    # Regex patterns
    _PATTERN_JOIN = re.compile(
        r'\b(INNER|LEFT|RIGHT|OUTER|FULL)?\s*JOIN\b',
        re.IGNORECASE
    )
    _PATTERN_SUBQUERY = re.compile(
        r'\bSELECT\b.*?\bFROM\b.*?\(\s*\bSELECT\b',
        re.IGNORECASE | re.DOTALL
    )
    _PATTERN_CORRELATED = re.compile(
        r'\bWHERE\b.*?\bIN\b\s*\(\s*\bSELECT\b.*?\bWHERE\b',
        re.IGNORECASE | re.DOTALL
    )
    _PATTERN_EXISTS = re.compile(
        r'\bEXISTS\s*\(\s*\bSELECT\b',
        re.IGNORECASE
    )
    _PATTERN_CORRELATED_REF = re.compile(
        r'\b\w+\.\w+\b'  # table.column pattern
    )
    _PATTERN_LEADING_WILDCARD = re.compile(
        r"\bLIKE\s+['\"]?%",  # LIKE '%' or LIKE "%
        re.IGNORECASE
    )
    _PATTERN_FUNCTION_IN_WHERE = re.compile(
        r'\bWHERE\b[^;]*?\w+\s*\(',  # WHERE followed by word + (
        re.IGNORECASE
    )
    _PATTERN_CARTESIAN = re.compile(
        r'\bFROM\b\s+[\w\[\]]+\s*,\s*[\w\[\]]+',  # FROM A, B without JOIN
        re.IGNORECASE
    )
    _PATTERN_DISTINCT = re.compile(r'\bDISTINCT\b', re.IGNORECASE)
    _PATTERN_ORDER_BY = re.compile(r'\bORDER\s+BY\b', re.IGNORECASE)
    _PATTERN_GROUP_BY = re.compile(r'\bGROUP\s+BY\b', re.IGNORECASE)
    _PATTERN_NOT_IN = re.compile(r'\bNOT\s+IN\b', re.IGNORECASE)
    _PATTERN_OR = re.compile(r'\bWHERE\b[^;]*?\bOR\b', re.IGNORECASE | re.DOTALL)
    _PATTERN_UNION = re.compile(r'\bUNION\b', re.IGNORECASE)
    _PATTERN_AGGREGATES = re.compile(
        r'\b(COUNT|SUM|AVG|MIN|MAX)\s*\(',
        re.IGNORECASE
    )
    _PATTERN_TABLE_EXTRACT = re.compile(
        r'\bFROM\b\s+([\w\[\]]+)|\bJOIN\b\s+([\w\[\]]+)',
        re.IGNORECASE
    )
    _PATTERN_NON_SELECT = re.compile(
        r'^\s*(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE)',
        re.IGNORECASE
    )

    @staticmethod
    def parse(sql: str) -> SQLParseResult | None:
        """Parse SQL and return complexity analysis result.

        Returns None for non-SELECT statements.
        """
        if not sql or not sql.strip():
            return None

        # Check for non-SELECT statements
        if SQLComplexityAnalyzer._PATTERN_NON_SELECT.match(sql.strip()):
            return None

        # Normalize SQL
        normalized = sql.upper()

        # Detect patterns
        join_count = len(SQLComplexityAnalyzer._PATTERN_JOIN.findall(sql))
        has_subquery = bool(SQLComplexityAnalyzer._PATTERN_SUBQUERY.search(sql))
        # Correlated: IN subquery with WHERE, or EXISTS with outer table reference
        has_correlated = bool(SQLComplexityAnalyzer._PATTERN_CORRELATED.search(sql))
        if not has_correlated and SQLComplexityAnalyzer._PATTERN_EXISTS.search(sql):
            # Check if EXISTS subquery has a correlated reference (table.column)
            exists_match = SQLComplexityAnalyzer._PATTERN_EXISTS.search(sql)
            if exists_match:
                # Look for table.column pattern after EXISTS
                after_exists = sql[exists_match.end():]
                has_correlated = bool(SQLComplexityAnalyzer._PATTERN_CORRELATED_REF.search(after_exists))
        has_distinct = bool(SQLComplexityAnalyzer._PATTERN_DISTINCT.search(sql))
        has_order_by = bool(SQLComplexityAnalyzer._PATTERN_ORDER_BY.search(sql))
        has_group_by = bool(SQLComplexityAnalyzer._PATTERN_GROUP_BY.search(sql))
        has_aggregates = bool(SQLComplexityAnalyzer._PATTERN_AGGREGATES.search(sql))
        has_where_function = bool(SQLComplexityAnalyzer._PATTERN_FUNCTION_IN_WHERE.search(sql))
        has_leading_wildcard = bool(SQLComplexityAnalyzer._PATTERN_LEADING_WILDCARD.search(sql))
        has_cartesian = bool(SQLComplexityAnalyzer._PATTERN_CARTESIAN.search(sql))
        has_not_in = bool(SQLComplexityAnalyzer._PATTERN_NOT_IN.search(sql))
        has_or = bool(SQLComplexityAnalyzer._PATTERN_OR.search(sql))
        has_union = bool(SQLComplexityAnalyzer._PATTERN_UNION.search(sql))

        # Extract tables
        tables = []
        for match in SQLComplexityAnalyzer._PATTERN_TABLE_EXTRACT.finditer(sql):
            table = (match.group(1) or match.group(2))
            if table:
                # Strip brackets for Access-style [TableName]
                table = table.strip('[]')
                if table and table not in tables:
                    tables.append(table)

        # Calculate score
        score = 0
        score += join_count * WEIGHT_JOIN
        if has_subquery:
            score += WEIGHT_SUBQUERY
        if has_correlated:
            score += WEIGHT_CORRELATED
        if has_leading_wildcard:
            score += WEIGHT_LEADING_WILDCARD
        if has_where_function:
            score += WEIGHT_FUNCTION_IN_WHERE
        if has_cartesian:
            score += WEIGHT_CARTESIAN
        if has_distinct:
            score += WEIGHT_DISTINCT
        if has_order_by:
            score += WEIGHT_ORDER_BY
        if has_group_by:
            score += WEIGHT_GROUP_BY
        if has_not_in:
            score += WEIGHT_NOT_IN
        if has_or:
            score += WEIGHT_OR
        if has_union:
            score += WEIGHT_UNION
        if has_aggregates:
            score += WEIGHT_AGGREGATE

        # Determine complexity label
        if score <= SIMPLE_THRESHOLD:
            label: Literal["simple", "moderate", "complex", "heavy"] = "simple"
        elif score <= MODERATE_THRESHOLD:
            label = "moderate"
        elif score <= COMPLEX_THRESHOLD:
            label = "complex"
        else:
            label = "heavy"

        return SQLParseResult(
            tables_involved=tables,
            join_count=join_count,
            has_subquery=has_subquery,
            has_correlated_subquery=has_correlated,
            has_distinct=has_distinct,
            has_order_by=has_order_by,
            has_group_by=has_group_by,
            has_aggregates=has_aggregates,
            has_where_function=has_where_function,
            has_leading_wildcard_like=has_leading_wildcard,
            has_cartesian_join=has_cartesian,
            has_not_in=has_not_in,
            has_or_condition=has_or,
            has_union=has_union,
            score=score,
            complexity_label=label,
        )


class SchemaAnalyzer:
    """Static analyzer for database schema analysis."""

    @staticmethod
    def analyze(adapter, table_names: list[str]) -> dict:
        """Analyze schema using adapter.

        Args:
            adapter: Database adapter (WinComAdapter or OdbcAdapter)
            table_names: List of table names to analyze

        Returns:
            dict with analysis results including indexed_columns
        """
        result = {
            "success": True,
            "table_count": 0,
            "indexed_columns": {},
            "index_info_available": True,
        }

        if not table_names:
            return result

        try:
            tables = adapter.get_tables()
            schema_plan, _ = adapter.get_table_schema_plan()

            result["table_count"] = len(table_names)

            # Build indexed columns map
            indexed_columns = {}
            for schema in schema_plan:
                if schema.name in table_names:
                    for index in schema.indexes:
                        for col in index.columns:
                            if schema.name not in indexed_columns:
                                indexed_columns[schema.name] = []
                            indexed_columns[schema.name].append(col)

            result["indexed_columns"] = indexed_columns
            result["index_info_available"] = len(indexed_columns) > 0

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            result["index_info_available"] = False

        return result


def generate_recommendations(parse_result: SQLParseResult, schema: dict, execution: dict | None, sql: str = "") -> list[str]:
    """Generate human-readable performance recommendations based on analysis.

    Args:
        parse_result: Result from SQLComplexityAnalyzer.parse()
        schema: Result from SchemaAnalyzer.analyze()
        execution: Execution timing info dict or None
        sql: Original SQL query string (optional, for detailed recommendations)

    Returns:
        List of recommendation strings
    """
    recommendations = []
    indexed_columns = schema.get("indexed_columns", {})

    # Missing index: column in WHERE/JOIN but not indexed
    tables = parse_result.tables_involved
    # Extract columns if there's a WHERE clause (with or without function) or JOINs
    has_where_clause = 'WHERE' in sql.upper()
    where_columns = _extract_where_columns(parse_result, sql) if (parse_result.has_where_function or has_where_clause or parse_result.join_count > 0) else []
    for table in tables:
        table_cols = indexed_columns.get(table, [])
        for col in where_columns:
            if col not in table_cols and table not in ("", None):
                recommendations.append(
                    f"Missing index on {table}.{col} — column used in WHERE/JOIN but not indexed"
                )
                break

    # Leading wildcard LIKE
    if parse_result.has_leading_wildcard_like:
        recommendations.append(
            "LIKE with leading wildcard in WHERE clause prevents index usage on column(s)"
        )

    # Cartesian join
    if parse_result.has_cartesian_join:
        recommendations.append(
            f"Cartesian join detected between {tables} — missing JOIN condition?"
        )

    # Correlated subquery
    if parse_result.has_correlated_subquery:
        recommendations.append(
            "Correlated subquery detected — consider rewriting as JOIN for better performance"
        )

    # NOT IN
    if parse_result.has_not_in:
        recommendations.append(
            "NOT IN detected — consider NOT EXISTS or LEFT JOIN as alternative"
        )

    # Function in WHERE - extract actual function name if SQL provided
    if parse_result.has_where_function:
        func_matches = _extract_function_names(sql) if sql else []
        if func_matches:
            for func_name, col_name in func_matches:
                recommendations.append(
                    f"Function {func_name}() in WHERE clause prevents index usage on {col_name}"
                )
        else:
            recommendations.append(
                "Function in WHERE clause prevents index usage on column(s)"
            )

    # OR condition
    if parse_result.has_or_condition:
        recommendations.append(
            "OR condition in WHERE clause — Access may not optimize this, consider UNION"
        )

    # Many joins
    if parse_result.join_count >= 5:
        recommendations.append(
            f"Join count ({parse_result.join_count}) is high — verify all joins have indexed columns"
        )

    # Aggregates on large table
    if parse_result.has_aggregates and execution:
        rows_total = execution.get("rows_total")
        if rows_total is not None and rows_total > 100000:
            recommendations.append(
                f"Aggregate functions on large table ({tables[0] if tables else 'unknown'}, "
                f"{execution['rows_total']} rows) — consider filters"
            )

    # Clean query
    if not recommendations:
        recommendations.append("No significant performance issues detected")

    # Add timing note if available
    if execution:
        duration = execution.get("duration_ms")
        rows_total = execution.get("rows_total")

        if duration is not None and duration > 0:
            # Could add timing-based recommendations here if needed
            pass

        if rows_total is not None and rows_total > 0:
            recommendations.append(
                f"Query returns {rows_total} rows from table(s) — consider pagination if too large"
            )

    return recommendations


def _extract_where_columns(parse_result: SQLParseResult, sql: str = "") -> list[str]:
    """Extract column names that appear in WHERE/JOIN conditions.

    Args:
        parse_result: SQLParseResult with table info
        sql: Original SQL query

    Returns:
        List of column names found in WHERE/JOIN
    """
    if not sql:
        return []

    columns = []
    # Extract columns from WHERE clause - match word patterns after =, >, <, LIKE, etc.
    where_pattern = re.compile(r'\bWHERE\b.*?(?:GROUP\s+BY|ORDER\s+BY|HAVING|$)', re.IGNORECASE | re.DOTALL)
    join_pattern = re.compile(r'\bJOIN\b\s+\w+\s+ON\s+([^()]+?)(?:\s+JOIN|\s+WHERE|GROUP|ORDER|HAVING|$)', re.IGNORECASE | re.DOTALL)

    # Extract from WHERE
    where_match = where_pattern.search(sql)
    if where_match:
        where_clause = where_match.group(0)
        # Find column references (table.column or just column)
        col_pattern = re.compile(r'\b(?:t\d+|o|c|a|ord|cust|p|prod|cat|sup|ship|s)\.([\w]+)|([\w]+)(?=\s*(?:=|>|<|LIKE|IN|IS|AND|OR))', re.IGNORECASE)
        for match in col_pattern.finditer(where_clause):
            col = match.group(1) or match.group(2)
            if col and col.upper() not in ('AND', 'OR', 'NOT', 'IN', 'IS', 'NULL', 'TRUE', 'FALSE'):
                columns.append(col)

    # Extract from JOIN conditions
    for match in join_pattern.finditer(sql):
        join_clause = match.group(1)
        col_pattern = re.compile(r'\b([\w]+)\s*=\s*([\w]+)', re.IGNORECASE)
        for m in col_pattern.finditer(join_clause):
            # Get the column part after the equals
            for part in [m.group(1), m.group(2)]:
                if '.' in part:
                    col = part.split('.')[-1]
                    columns.append(col)
                else:
                    columns.append(part)

    return list(set(columns))


def _extract_function_names(sql: str) -> list[tuple[str, str]]:
    """Extract function names and their columns from WHERE clause.

    Returns list of (function_name, column_name) tuples.
    """
    results = []
    if not sql:
        return results
    # Pattern to match function() in WHERE clause: YEAR(column), UPPER(column), etc.
    pattern = re.compile(r'\b(WEEKDAY|YEAR|MONTH|DAY|HOUR|MINUTE|SECOND|UPPER|LOWER|TRIM|LTRIM|RTRIM|LEFT|RIGHT|MID|LEN|COUNT|SUM|AVG|MIN|MAX)\s*\(\s*([\w.]+)\s*\)', re.IGNORECASE)
    for match in pattern.finditer(sql):
        func_name = match.group(1).upper()
        column_name = match.group(2)
        results.append((func_name, column_name))
    return results


class QueryAnalyzerService:
    """Orchestrator service for SQL query analysis."""

    @staticmethod
    def analyze(
        sql: str,
        params: list | None,
        adapter,
        dry_run: bool = False,
        sample_size: int = 0,
    ) -> dict:
        """Analyze a SQL query for complexity, schema, and performance.

        Args:
            sql: SQL query string
            params: Query parameters
            adapter: Database adapter (WinComAdapter or OdbcAdapter)
            dry_run: If True, skip actual query execution
            sample_size: Number of rows to sample (0 = no sampling)

        Returns:
            dict with keys: success, query, execution, complexity, schema_analysis, recommendations
        """
        result = {
            "success": True,
            "query": sql,
            "execution": {
                "duration_ms": None,
                "rows_total": None,
                "sample_size": sample_size,
                "sampled_data": None,
                "error": None,
            },
            "complexity": None,
            "schema_analysis": None,
            "recommendations": [],
        }

        # Step 1: Parse SQL complexity
        parse_result = SQLComplexityAnalyzer.parse(sql)
        if parse_result is None:
            result["success"] = False
            result["error"] = "Not a SELECT statement"
            return result

        # Build complexity dict
        result["complexity"] = {
            "tables_involved": parse_result.tables_involved,
            "join_count": parse_result.join_count,
            "has_subquery": parse_result.has_subquery,
            "has_correlated_subquery": parse_result.has_correlated_subquery,
            "has_distinct": parse_result.has_distinct,
            "has_order_by": parse_result.has_order_by,
            "has_group_by": parse_result.has_group_by,
            "has_aggregates": parse_result.has_aggregates,
            "has_where_function": parse_result.has_where_function,
            "has_leading_wildcard_like": parse_result.has_leading_wildcard_like,
            "has_cartesian_join": parse_result.has_cartesian_join,
            "has_not_in": parse_result.has_not_in,
            "has_or_condition": parse_result.has_or_condition,
            "has_union": parse_result.has_union,
            "score": parse_result.score,
            "complexity_label": parse_result.complexity_label,
        }

        # Step 2: Get tables involved and analyze schema
        tables_involved = parse_result.tables_involved
        try:
            result["schema_analysis"] = SchemaAnalyzer.analyze(adapter, tables_involved)
        except Exception as e:
            result["schema_analysis"] = {
                "success": False,
                "error": str(e),
                "table_count": len(tables_involved),
                "indexed_columns": {},
                "index_info_available": False,
            }

        # Step 3: Execution timing (unless dry_run)
        if not dry_run:
            # 3a: Execute COUNT(*) to get row count and timing
            count_sql = f"SELECT COUNT(*) AS _cnt FROM ({sql}) AS _q"
            start_time = time.perf_counter()
            try:
                count_result = adapter.execute_query(count_sql, params)
                rows_data = list(count_result)
                end_time = time.perf_counter()
                result["execution"]["duration_ms"] = (end_time - start_time) * 1000
                result["execution"]["rows_total"] = rows_data[0]["_cnt"] if rows_data else 0
            except Exception as e:
                result["execution"]["error"] = f"COUNT execution failed: {str(e)}"

            # 3b: Sample data if requested
            if sample_size > 0 and result["execution"]["rows_total"] is not None:
                sample_sql = f"SELECT TOP {sample_size} * FROM ({sql}) AS _s"
                try:
                    sample_result = adapter.execute_query(sample_sql, params)
                    result["execution"]["sampled_data"] = list(sample_result)
                except Exception as e:
                    if result["execution"]["error"]:
                        result["execution"]["error"] += f"; Sample failed: {str(e)}"
                    else:
                        result["execution"]["error"] = f"Sample failed: {str(e)}"

        # Step 4: Generate recommendations
        result["recommendations"] = generate_recommendations(
            parse_result,
            result["schema_analysis"],
            result["execution"],
            sql=sql,
        )

        return result
