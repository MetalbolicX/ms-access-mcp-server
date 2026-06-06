"""Tests for topological_sorter module — RED phase."""

from __future__ import annotations

import pytest
from ms_access_mcp.services.topological_sorter import sort_tables_by_fk
from ms_access_mcp.models.migration import TableSchema, ColumnSchema, ForeignKeySchema


def make_table(name: str, foreign_keys: list[ForeignKeySchema] | None = None) -> TableSchema:
    """Helper to create a TableSchema with minimal columns."""
    return TableSchema(
        name=name,
        columns=[ColumnSchema(name="id", source_type="Integer")],
        foreign_keys=foreign_keys or [],
    )


class TestSortTablesByFk:
    def test_empty_list_returns_empty_list(self):
        result = sort_tables_by_fk([])
        assert result == []

    def test_single_table_returns_same_list(self):
        table = make_table("Customers")
        result = sort_tables_by_fk([table])
        assert len(result) == 1
        assert result[0].name == "Customers"

    def test_tables_no_fk_dependencies_returns_original_order(self):
        """Tables without FK refs should maintain insertion order."""
        customers = make_table("Customers")
        products = make_table("Products")
        result = sort_tables_by_fk([customers, products])
        assert [t.name for t in result] == ["Customers", "Products"]

    def test_fk_dependency_parent_before_child(self):
        """Parent table (referenced by FK) must come before child table."""
        customers = make_table("Customers")
        orders = make_table("Orders", foreign_keys=[
            ForeignKeySchema(name="FK_Customer", columns=["customer_id"], referenced_table="Customers", referenced_columns=["id"])
        ])
        result = sort_tables_by_fk([orders, customers])  # reversed input
        assert [t.name for t in result] == ["Customers", "Orders"]

    def test_deep_fk_chain(self):
        """Three-level chain: Country → Customer → Order."""
        country = make_table("Country")
        customer = make_table("Customer", foreign_keys=[
            ForeignKeySchema(name="FK_Country", columns=["country_id"], referenced_table="Country", referenced_columns=["id"])
        ])
        order = make_table("Order", foreign_keys=[
            ForeignKeySchema(name="FK_Customer", columns=["customer_id"], referenced_table="Customer", referenced_columns=["id"])
        ])
        # Reversed order input
        result = sort_tables_by_fk([order, customer, country])
        assert [t.name for t in result] == ["Country", "Customer", "Order"]

    def test_mn_junction_after_both_parents(self):
        """M:N junction table (StudentCourses) must come after both parents (Students, Courses)."""
        students = make_table("Students")
        courses = make_table("Courses")
        student_courses = make_table("StudentCourses", foreign_keys=[
            ForeignKeySchema(name="FK_Student", columns=["student_id"], referenced_table="Students", referenced_columns=["id"]),
            ForeignKeySchema(name="FK_Course", columns=["course_id"], referenced_table="Courses", referenced_columns=["id"]),
        ])
        # Random input order
        result = sort_tables_by_fk([student_courses, courses, students])
        # Junction must be last
        assert result[-1].name == "StudentCourses"
        # Parents must come before junction
        assert result[0].name in ("Students", "Courses")
        assert result[1].name in ("Students", "Courses")
        assert result[0].name != result[1].name