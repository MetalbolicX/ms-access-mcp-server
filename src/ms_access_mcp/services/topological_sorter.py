"""Topological sorter — pure graph algorithm for sorting tables by FK dependency."""

from __future__ import annotations

from copy import deepcopy


def sort_tables_by_fk(tables: list) -> list:
    """Sort tables so parent tables (referenced by FK) are created before children.

    Handles M:N via junction tables: two 1:N relationships are resolved
    independently, so the junction table naturally comes after both parents.
    """
    tables_by_name = {t.name: t for t in tables}
    fk_refs: dict[str, set[str]] = {}
    for t in tables:
        refs = set()
        for fk in t.foreign_keys:
            if fk.referenced_table in tables_by_name:
                refs.add(fk.referenced_table)
        fk_refs[t.name] = refs

    sorted_names: list[str] = []
    visited: set[str] = set()

    def _visit(name: str) -> None:
        if name in visited:
            return
        visited.add(name)
        for dep in fk_refs.get(name, set()):
            _visit(dep)
        sorted_names.append(name)

    for t in tables:
        _visit(t.name)

    return [deepcopy(tables_by_name[n]) for n in sorted_names]