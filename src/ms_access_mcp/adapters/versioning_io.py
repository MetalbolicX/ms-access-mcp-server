"""Versioning export/import/compare operations for COM automation.

Extracted from WinComAdapter to respect SRP.
"""

import hashlib
import os
import tempfile
from typing import Any, Callable

from ..adapters.com_dispatcher import ComDispatcher


class VersioningIo:
    """Versioning operations — export, import, compare Access objects.

    Args:
        dispatcher: ComDispatcher instance for STA-threaded COM calls.
        save_text: Callable for SaveAsText(object_type, object_name) → str
        load_text: Callable for LoadFromText(object_type, object_name, text_data) → bool
        get_tables_fn: Callable returning list[TableInfo]
        get_relationships_fn: Callable returning list[RelationshipInfo]
        get_system_tables_fn: Callable returning list[TableInfo]
    """

    def __init__(
        self,
        dispatcher: ComDispatcher,
        save_text: Callable[[int, str], str] | None = None,
        load_text: Callable[[int, str, str], bool] | None = None,
        get_tables_fn: Callable[[], list] | None = None,
        get_relationships_fn: Callable[[], list] | None = None,
        get_system_tables_fn: Callable[[], list] | None = None,
    ) -> None:
        self._dispatcher = dispatcher
        self._save_text = save_text
        self._load_text = load_text
        self._get_tables = get_tables_fn
        self._get_relationships = get_relationships_fn
        self._get_system_tables = get_system_tables_fn

    # ------------------------------------------------------------------ #
    # Module export (VBA code — in-memory, not SaveAsText)
    # ------------------------------------------------------------------ #

    def export_module_to_text(self, module_name: str) -> str:
        """Export VBA module code as plain text."""
        if not self._dispatcher._started:
            return ""

        def _do() -> str:
            vbe = self._dispatcher.access_app.VBE
            try:
                for i in range(1, vbe.VBProjects.Count + 1):
                    vb_project = vbe.VBProjects(i)
                    for comp in vb_project.VBComponents:
                        if comp.Name == module_name:
                            lines = comp.CodeModule.CountOfLines
                            if lines > 0:
                                return comp.CodeModule.Lines(1, lines)
                            return ""
            except Exception:
                pass
            return ""

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # Macro export/import (SaveAsText acMacro=8)
    # ------------------------------------------------------------------ #

    def export_macro_to_text(self, macro_name: str) -> str:
        """Export a macro to text representation via SaveAsText(acMacro=8)."""
        if not self._dispatcher._started:
            return ""

        def _do() -> str:
            if self._save_text:
                return self._save_text(8, macro_name)
            # Fallback: direct SaveAsText
            temp_path = None
            try:
                fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix="mcp_exp_")
                os.close(fd)
                self._dispatcher.access_app.SaveAsText(8, macro_name, temp_path)
                with open(temp_path, "rb") as f:
                    raw = f.read()
                content = raw.decode("utf-16-le", errors="replace").lstrip("\ufeff")
                return content
            except Exception:
                return ""
            finally:
                if temp_path:
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass

        return self._dispatcher.call(_do)

    def import_macro_from_text(self, macro_name: str, macro_data: str) -> bool:
        """Import a macro from text data via LoadFromText(acMacro=8)."""
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            if self._load_text:
                return self._load_text(8, macro_name, macro_data)
            # Fallback: direct LoadFromText
            temp_path = None
            try:
                fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix="mcp_imp_")
                os.close(fd)
                with open(temp_path, "wb") as f:
                    f.write(b"\xff\xfe")
                    f.write(macro_data.encode("utf-16-le"))
                self._dispatcher.access_app.LoadFromText(8, macro_name, temp_path)
                return True
            except Exception:
                return False
            finally:
                if temp_path:
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # Query export/import (SaveAsText acQuery=5)
    # ------------------------------------------------------------------ #

    def export_query_to_text(self, query_name: str) -> str:
        """Export a query to text using SaveAsText(acQuery=5, query_name, temp_path).

        Returns the text content or empty string on failure.
        """
        if not self._dispatcher._started:
            return ""

        def _do() -> str:
            if self._save_text:
                return self._save_text(5, query_name)
            # Fallback: direct SaveAsText
            temp_path = None
            try:
                fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix="mcp_exp_")
                os.close(fd)
                self._dispatcher.access_app.SaveAsText(5, query_name, temp_path)
                with open(temp_path, "rb") as f:
                    raw = f.read()
                content = raw.decode("utf-16-le", errors="replace").lstrip("\ufeff")
                return content
            except Exception:
                return ""
            finally:
                if temp_path:
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass

        return self._dispatcher.call(_do)

    def import_query_from_text(self, query_name: str, query_data: str) -> bool:
        """Import a query from text data using LoadFromText(acQuery=5, ...).

        Returns True on success, False on failure.
        """
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            if self._load_text:
                return self._load_text(5, query_name, query_data)
            # Fallback: direct LoadFromText
            temp_path = None
            try:
                fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix="mcp_imp_")
                os.close(fd)
                with open(temp_path, "wb") as f:
                    f.write(b"\xff\xfe")
                    f.write(query_data.encode("utf-16-le"))
                self._dispatcher.access_app.LoadFromText(5, query_name, temp_path)
                return True
            except Exception:
                return False
            finally:
                if temp_path:
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass

        return self._dispatcher.call(_do)

    # ------------------------------------------------------------------ #
    # Export all versioning (forms, reports, modules, macros, queries)
    # ------------------------------------------------------------------ #

    def export_all_versioning(
        self,
        output_dir: str,
        *,
        dedup: bool = True,
        module_ext: str = ".bas",
        get_forms_fn: Callable[[], list] | None = None,
        get_reports_fn: Callable[[], list] | None = None,
        get_modules_fn: Callable[[], list] | None = None,
        get_macros_fn: Callable[[], list] | None = None,
        get_queries_fn: Callable[[], list] | None = None,
        export_form_to_text_fn: Callable[[str], str] | None = None,
        export_report_to_text_fn: Callable[[str], str] | None = None,
        hash_content_fn: Callable[[str], str] | None = None,
    ) -> dict:
        """Export all forms, reports, modules, macros, and queries to a directory structure.

        Args:
            output_dir: Root directory for export
            dedup: If True, skip export when SHA256 of content matches existing file (default True)
            module_ext: Extension for module files, '.bas' (default) or '.txt'
            get_forms_fn: Callable returning list[FormInfo]
            get_reports_fn: Callable returning list[ReportInfo]
            get_modules_fn: Callable returning list[ModuleInfo]
            get_macros_fn: Callable returning list[MacroInfo]
            get_queries_fn: Callable returning list[QueryInfo]
            export_form_to_text_fn: Callable[[str], str] for form text export
            export_report_to_text_fn: Callable[[str], str] for report text export
            hash_content_fn: Callable[[str], str] for SHA256 hashing
        """
        if not self._dispatcher._started:
            return {"success": False, "error": "Not connected to database", "exported": {}}

        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            return {"success": False, "error": f"Cannot create directory: {e}", "exported": {}}

        def safe_filename(name: str) -> str:
            for ch in '\\/:*?"<>|':
                name = name.replace(ch, '_')
            return name

        exported = {"forms": [], "reports": [], "modules": [], "macros": [], "queries": []}

        # Helper: SHA256 file hash
        def _file_hash(path: str) -> str:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                h.update(f.read())
            return h.hexdigest()

        # Helper: compute content hash for a string
        def _hash_content(content: str) -> str:
            if hash_content_fn:
                return hash_content_fn(content)
            return hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Helper: export via COM SaveAsText and return (success, sha256_of_new_content, skipped)
        def _export_and_hash(object_type: int, name: str, out_path: str) -> tuple[bool, str, bool]:
            """Export via COM SaveAsText, return (success, sha256_of_new_content, skipped)."""
            temp_path = None
            try:
                fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix="mcp_exp_")
                os.close(fd)
                self._dispatcher.access_app.SaveAsText(object_type, name, temp_path)
                with open(temp_path, "rb") as f:
                    raw = f.read()
                content = raw.decode("utf-16-le", errors="replace").lstrip("\ufeff")
                h = hashlib.sha256(content.encode("utf-8")).hexdigest()
                # Check if we should skip (dedup enabled and content unchanged)
                skip = False
                if dedup and os.path.exists(out_path):
                    existing_hash = _file_hash(out_path)
                    if existing_hash == h:
                        skip = True
                if not skip:
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(content)
                return True, h, skip
            except Exception:
                return False, "", False
            finally:
                if temp_path:
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass

        # ── Export forms ──────────────────────────────────────────────────────
        if get_forms_fn:
            try:
                forms = get_forms_fn()
                forms_dir = os.path.join(output_dir, "forms")
                os.makedirs(forms_dir, exist_ok=True)
                for form in forms:
                    try:
                        safe_name = safe_filename(form.name)
                        out_path = os.path.join(forms_dir, f"forms_{safe_name}.txt")
                        success, new_hash, skipped = _export_and_hash(2, form.name, out_path)
                        if success and not skipped:
                            exported["forms"].append(form.name)
                    except Exception:
                        pass
            except Exception:
                pass

        # ── Export reports ───────────────────────────────────────────────────
        if get_reports_fn:
            try:
                reports = get_reports_fn()
                reports_dir = os.path.join(output_dir, "reports")
                os.makedirs(reports_dir, exist_ok=True)
                for report in reports:
                    try:
                        safe_name = safe_filename(report.name)
                        out_path = os.path.join(reports_dir, f"reports_{safe_name}.txt")
                        success, new_hash, skipped = _export_and_hash(4, report.name, out_path)
                        if success and not skipped:
                            exported["reports"].append(report.name)
                    except Exception:
                        pass
            except Exception:
                pass

        # ── Export VBA modules (in-memory, use _hash_content) ───────────────
        if get_modules_fn:
            try:
                modules = get_modules_fn()
                modules_dir = os.path.join(output_dir, "modules")
                os.makedirs(modules_dir, exist_ok=True)
                for mod in modules:
                    try:
                        safe_name = safe_filename(mod.name)
                        out_path = os.path.join(modules_dir, f"modules_{safe_name}{module_ext}")
                        content = mod.code or ""

                        if dedup and os.path.exists(out_path):
                            # SHA256 existing file vs in-memory content
                            existing_hash = _file_hash(out_path)
                            new_hash = _hash_content(content)
                            if existing_hash == new_hash:
                                # Skip — content unchanged
                                pass
                            else:
                                with open(out_path, "w", encoding="utf-8") as f:
                                    f.write(content)
                                exported["modules"].append(mod.name)
                        else:
                            with open(out_path, "w", encoding="utf-8") as f:
                                f.write(content)
                            exported["modules"].append(mod.name)
                    except Exception:
                        pass
            except Exception:
                pass

        # ── Export macros (static text, use _hash_content) ──────────────────
        if get_macros_fn:
            try:
                macros = get_macros_fn()
                macros_dir = os.path.join(output_dir, "macros")
                os.makedirs(macros_dir, exist_ok=True)
                for macro in macros:
                    try:
                        safe_name = safe_filename(macro.name)
                        out_path = os.path.join(macros_dir, f"macros_{safe_name}.txt")
                        content = f"Macro: {macro.name}\nType: Access Macro\n"

                        if dedup and os.path.exists(out_path):
                            existing_hash = _file_hash(out_path)
                            new_hash = _hash_content(content)
                            if existing_hash == new_hash:
                                pass
                            else:
                                with open(out_path, "w", encoding="utf-8") as f:
                                    f.write(content)
                                exported["macros"].append(macro.name)
                        else:
                            with open(out_path, "w", encoding="utf-8") as f:
                                f.write(content)
                            exported["macros"].append(macro.name)
                    except Exception:
                        pass
            except Exception:
                pass

        # ── Export queries (SaveAsText acQuery=5) ──────────────────────────────
        if get_queries_fn:
            try:
                queries = get_queries_fn()
                queries_dir = os.path.join(output_dir, "queries")
                os.makedirs(queries_dir, exist_ok=True)
                for query in queries:
                    try:
                        safe_name = safe_filename(query.name)
                        out_path = os.path.join(queries_dir, f"queries_{safe_name}.txt")
                        success, new_hash, skipped = _export_and_hash(5, query.name, out_path)
                        if success and not skipped:
                            exported["queries"].append(query.name)
                    except Exception:
                        pass
            except Exception:
                pass

        total = sum(len(v) for v in exported.values())

        return {
            "success": True,
            "exported": exported,
            "output_dir": output_dir,
            "file_count": total,
        }

    # ------------------------------------------------------------------ #
    # Compare versioning
    # ------------------------------------------------------------------ #

    @staticmethod
    def _hash_file(file_path: str) -> str:
        """Compute SHA256 hexdigest of a file's content."""
        if not os.path.exists(file_path):
            return ""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            h.update(f.read())
        return h.hexdigest()

    @staticmethod
    def _hash_content(content: str) -> str:
        """Compute SHA256 hexdigest of a string (in-memory VBA code, etc.)."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def compare_versioning(
        self,
        export_dir: str,
        get_forms_fn: Callable[[], list] | None = None,
        get_reports_fn: Callable[[], list] | None = None,
        get_modules_fn: Callable[[], list] | None = None,
        get_macros_fn: Callable[[], list] | None = None,
        get_queries_fn: Callable[[], list] | None = None,
        export_form_to_text_fn: Callable[[str], str] | None = None,
        export_report_to_text_fn: Callable[[str], str] | None = None,
        export_macro_to_text_fn: Callable[[str], str] | None = None,
        export_query_to_text_fn: Callable[[str], str] | None = None,
        export_module_to_text_fn: Callable[[str], str] | None = None,
    ) -> dict:
        """Compare objects in the DB against exported files in export_dir.

        Returns dict with:
          - new: objects in DB but not in export_dir
          - missing: objects in export_dir but not in DB
          - changed: objects in both but content differs
          - unchanged: objects in both with identical content
        Each entry: {"type": "form"|"report"|"module"|"macro"|"query", "name": str}
        """
        if not self._dispatcher._started:
            return {"new": [], "missing": [], "changed": [], "unchanged": []}

        def safe_name(name: str) -> str:
            for ch in '\\/:*?"<>|':
                name = name.replace(ch, '_')
            return name

        result: dict[str, list] = {"new": [], "missing": [], "changed": [], "unchanged": []}

        subdirs = {
            "forms": (2, "forms", get_forms_fn),
            "reports": (4, "reports", get_reports_fn),
            "modules": (5, "modules", get_modules_fn),
            "macros": (8, "macros", get_macros_fn),
            "queries": (5, "queries", get_queries_fn),
        }

        for obj_type, (_, dir_name, getter) in subdirs.items():
            dir_path = os.path.join(export_dir, dir_name)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                continue

            # Collect exported file names
            exported_files: dict[str, str] = {}
            if os.path.isdir(dir_path):
                for fname in os.listdir(dir_path):
                    if fname.endswith(".txt") or fname.endswith(".bas"):
                        # e.g. forms_frmMain.txt → frmMain
                        parts = fname.split("_", 1)
                        if len(parts) == 2:
                            exported_files[parts[1]] = os.path.join(dir_path, fname)

            # Scan DB objects
            db_objects: list = []
            if getter:
                try:
                    db_objects = getter()
                except Exception:
                    db_objects = []

            for obj in db_objects:
                obj_name = safe_name(obj.name)
                file_pattern = f"{dir_name}_{obj_name}"
                matching_files = [
                    f for f in os.listdir(dir_path)
                    if f.startswith(file_pattern)
                ]

                if not matching_files:
                    # In DB, not in export
                    result["new"].append({"type": obj_type.rstrip("s"), "name": obj.name})
                else:
                    # Check content
                    file_path = os.path.join(dir_path, matching_files[0])
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            file_content = f.read()
                    except Exception:
                        file_content = ""

                    # Get DB content for comparison
                    db_content = ""
                    if obj_type in ("modules",):
                        db_content = getattr(obj, "code", "") or ""
                    else:
                        # For forms/reports/macros/queries, read via export
                        if obj_type == "forms" and export_form_to_text_fn:
                            db_content = export_form_to_text_fn(obj.name)
                        elif obj_type == "reports" and export_report_to_text_fn:
                            db_content = export_report_to_text_fn(obj.name)
                        elif obj_type == "macros" and export_macro_to_text_fn:
                            db_content = export_macro_to_text_fn(obj.name)
                        elif obj_type == "queries" and export_query_to_text_fn:
                            db_content = export_query_to_text_fn(obj.name)

                    if db_content == file_content:
                        result["unchanged"].append({"type": obj_type.rstrip("s"), "name": obj.name})
                    else:
                        result["changed"].append({"type": obj_type.rstrip("s"), "name": obj.name})

            # Find missing (in export but not in DB)
            for fname in os.listdir(dir_path):
                if fname.startswith(f"{dir_name}_"):
                    parts = fname.split("_", 1)
                    if len(parts) == 2:
                        obj_name = parts[1]
                        # Check if it's in DB
                        in_db = False
                        if db_objects:
                            in_db = any(
                                safe_name(obj.name) == safe_name(obj_name)
                                for obj in db_objects
                            )
                        if not in_db:
                            result["missing"].append({
                                "type": obj_type.rstrip("s"),
                                "name": obj_name.rsplit(".", 1)[0],  # strip extension
                            })

        return result

    # ------------------------------------------------------------------ #
    # Import all versioning
    # ------------------------------------------------------------------ #

    def import_all_versioning(
        self,
        input_dir: str,
        get_modules_fn: Callable[[], list] | None = None,
        set_vba_code_fn: Callable[[str, str], bool] | None = None,
        compile_vba_fn: Callable[[], dict] | None = None,
        import_form_from_text_fn: Callable[[str, str], bool] | None = None,
        import_report_from_text_fn: Callable[[str, str], bool] | None = None,
        import_macro_from_text_fn: Callable[[str, str], bool] | None = None,
        import_query_from_text_fn: Callable[[str, str], bool] | None = None,
    ) -> dict:
        """Import all objects from an exported versioning directory.

        Ordering: modules → forms/reports → macros → queries.
        Returns dict with per-type results and overall success.
        """
        if not self._dispatcher._started:
            return {"success": False, "error": "Not connected to database", "imported": {}}

        if not os.path.isdir(input_dir):
            return {"success": False, "error": f"Directory not found: {input_dir}", "imported": {}}

        def safe_read_file(path: str) -> str:
            """Read file: detect BOM for UTF-16-LE, else decode as UTF-8."""
            try:
                with open(path, "rb") as f:
                    raw = f.read()
                if len(raw) >= 2 and raw[0] == 0xff and raw[1] == 0xfe:
                    return raw.decode("utf-16-le", errors="replace").lstrip("\ufeff")
                return raw.decode("utf-8", errors="replace")
            except Exception:
                return ""

        imported: dict[str, list] = {"modules": [], "forms": [], "reports": [], "macros": [], "queries": []}
        errors: list[str] = []

        subdirs = [
            ("modules", "modules", ".bas", ".txt"),
            ("forms", "forms", ".txt", ".txt"),
            ("reports", "reports", ".txt", ".txt"),
            ("macros", "macros", ".txt", ".txt"),
            ("queries", "queries", ".txt", ".txt"),
        ]

        for type_key, dir_name, ext, _ in subdirs:
            dir_path = os.path.join(input_dir, dir_name)
            if not os.path.isdir(dir_path):
                continue

            # Collect files in this subdir, validate all exist first
            files_to_import: list[tuple[str, str]] = []
            if os.path.isdir(dir_path):
                for fname in os.listdir(dir_path):
                    if fname.startswith(f"{dir_name}_") and (fname.endswith(ext) or fname.endswith(".bas")):
                        file_path = os.path.join(dir_path, fname)
                        if os.path.isfile(file_path):
                            files_to_import.append((fname, file_path))

            # Sort by name for deterministic order
            files_to_import.sort(key=lambda x: x[0])

            for fname, file_path in files_to_import:
                # Extract object name from filename
                # e.g. modules_modTest.bas → modTest
                name = fname[len(dir_name) + 1:]
                if name.endswith(".txt") or name.endswith(".bas"):
                    name = name[:name.rfind(".")]
                name = name.replace("_", " ")

                try:
                    data = safe_read_file(file_path)

                    if type_key == "modules":
                        if set_vba_code_fn:
                            ok = set_vba_code_fn(name, data)
                            if ok:
                                imported["modules"].append(name)
                            else:
                                errors.append(f"module {name}: set_vba_code failed")

                        if compile_vba_fn:
                            compile_result = compile_vba_fn()
                            if not compile_result.get("success"):
                                errors.append(f"module {name}: compile error")

                    elif type_key == "forms":
                        if import_form_from_text_fn:
                            success = import_form_from_text_fn(name, data)
                            if success:
                                imported["forms"].append(name)
                            else:
                                errors.append(f"form {name}: import failed")

                    elif type_key == "reports":
                        if import_report_from_text_fn:
                            success = import_report_from_text_fn(name, data)
                            if success:
                                imported["reports"].append(name)
                            else:
                                errors.append(f"report {name}: import failed")

                    elif type_key == "macros":
                        if import_macro_from_text_fn:
                            success = import_macro_from_text_fn(name, data)
                            if success:
                                imported["macros"].append(name)
                            else:
                                errors.append(f"macro {name}: import failed")

                    elif type_key == "queries":
                        if import_query_from_text_fn:
                            success = import_query_from_text_fn(name, data)
                            if success:
                                imported["queries"].append(name)
                            else:
                                errors.append(f"query {name}: import failed")

                except Exception as e:
                    errors.append(f"{type_key.rstrip('s')} {name}: {e}")

        return {
            "success": len(errors) == 0,
            "imported": imported,
            "errors": errors if errors else None,
        }

    # ------------------------------------------------------------------ #
    # Schema DDL export
    # ------------------------------------------------------------------ #

    def export_schema_ddl(self, output_dir: str) -> dict:
        """Export table schemas as DDL SQL files via COM introspection.

        Uses get_tables() and get_relationships() (both available via COM's DAO model).
        Generates CREATE TABLE and ALTER TABLE statements.

        Args:
            output_dir: Root directory for schema output

        Returns:
            dict with success, ddl_tables path, ddl_relationships path
        """
        if not self._dispatcher._started:
            return {"success": False, "error": "Not connected"}

        from pathlib import Path

        tables = self._get_tables() if self._get_tables else []
        relationships = self._get_relationships() if self._get_relationships else []

        schema_dir = Path(output_dir) / "schema"
        schema_dir.mkdir(parents=True, exist_ok=True)

        ddl_tables_path = schema_dir / "ddl_tables.sql"
        ddl_rels_path = schema_dir / "ddl_relationships.sql"

        with open(ddl_tables_path, "w", encoding="utf-8") as f:
            f.write("-- Access Table DDL\n-- Generated by ms-access-mcp-server\n\n")
            for table in tables:
                f.write(f"CREATE TABLE [{table.name}] (\n")
                col_defs = []
                for field in table.fields:
                    col_def = f"  [{field.name}] {field.type}"
                    if field.required:
                        col_def += " NOT NULL"
                    else:
                        col_def += " NULL"
                    col_defs.append(col_def)
                f.write(",\n".join(col_defs))
                f.write("\n);\n\n")

        with open(ddl_rels_path, "w", encoding="utf-8") as f:
            f.write("-- Access Relationship DDL\n-- Generated by ms-access-mcp-server\n\n")
            for rel in relationships:
                f.write(f"-- Relationship: {rel.name}\n")
                f.write(f"-- Table: {rel.table}, Foreign Table: {rel.foreign_table}\n")
                f.write(f"-- Attributes: {rel.attributes}\n")
                f.write(f"ALTER TABLE [{rel.table}] ADD CONSTRAINT [{rel.name}] ")
                f.write(f"FOREIGN KEY REFERENCES [{rel.foreign_table}];\n")

        return {
            "success": True,
            "ddl_tables": str(ddl_tables_path),
            "ddl_relationships": str(ddl_rels_path),
            "tables_exported": len(tables),
            "relationships_exported": len(relationships),
        }