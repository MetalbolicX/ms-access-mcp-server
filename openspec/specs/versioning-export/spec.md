# Versioning Export — Specification

## Purpose

Export Access database objects (forms, reports, VBA modules, macros) as text files suitable for version control (git). Enables tracking schema changes over time and code review workflows.

## Design

### MCP Tools

#### A) Batch Export Tool

**Tool:** `export_versioning`

**Input:**
```json
{
  "output_dir": "C:\\db\\exports\\v1"
}
```

**Output:**
```json
{
  "success": true,
  "exported": {
    "forms": ["Customers", "Orders"],
    "reports": ["Invoice", "Summary"],
    "modules": ["basUtils", "clsDataAccess", "Form_Customers"],
    "macros": ["mcrExportData"]
  },
  "output_dir": "C:\\db\\exports\\v1",
  "file_count": 11
}
```

**Behavior:**
- Creates `output_dir` if it doesn't exist
- Exports each object type into a subdirectory: `forms/`, `reports/`, `modules/`, `macros/`
- Files named `{type}_{name}.txt`, e.g. `forms_Customers.txt`, `modules_basUtils.txt`
- Uses Access `SaveAsText` for forms/reports (true binary-to-text conversion)
- Uses `CodeModule.Lines` for VBA module code
- Macros export as name only (Access macros are not code-exportable)
- Overwrites existing files without warning
- All or nothing — if any export fails, roll back directory creation (but already-written files remain)

**Directory structure:**
```
exports/v1/
├── forms/
│   ├── forms_Customers.txt
│   └── forms_Orders.txt
├── reports/
│   ├── reports_Invoice.txt
│   └── reports_Summary.txt
├── modules/
│   ├── modules_basUtils.txt
│   └── modules_clsDataAccess.txt
└── macros/
    └── macros_mcrExportData.txt
```

#### B) Individual Export Tools

**Tool:** `export_form_to_text(form_name: str) -> dict`
```json
{"success": true, "form": "Customers", "data": "..."}
```

**Tool:** `export_report_to_text(report_name: str) -> dict`
```json
{"success": true, "report": "Invoice", "data": "..."}
```

**Tool:** `export_module_to_text(module_name: str) -> dict`
```json
{"success": true, "module": "basUtils", "data": "Option Explicit\n\nPublic Function..."}
```

**Tool:** `export_macro_to_text(macro_name: str) -> dict`
```json
{"success": true, "macro": "mcrExportData", "data": "Macro: mcrExportData\nActions: 3"}
```

### Implementation Details

#### Access SaveAsText (DAO)

Access provides `Application.SaveAsText` which converts forms/reports to Unicode text format:

```python
# AcObjectType constants
acForm = 2
acReport = 4

# Export a form
access_app.SaveAsText(acForm, form_name, export_path)
```

The resulting `.txt` file contains the complete form definition including controls, properties, and VBA code embedded. This is the same format Access uses internally and for version control.

#### VBA Module Export

```python
vbe = self._access_app.VBE
vb_project = vbe.ActiveVBProject
for comp in vb_project.VBComponents:
    if comp.Name == module_name:
        code = comp.CodeModule.Lines(1, comp.CodeModule.CountOfLines)
        return code
```

#### Macro Export

Access macros cannot be exported as code. We export metadata only:
```python
name: str
type: "Macro"
# No code content available
```

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| Form/report not found | Return `success: false, error: "Not found"` |
| Module not found | Return `success: false, error: "Module not found"` |
| Form with no code module | Export succeeds with empty data section |
| Macro with no name | Skip (shouldn't happen) |
| Special chars in name | Replace `\/:*?"<>|` with `_` in filename |
| Empty database (no objects) | Return `success: true, exported: {}` |

### Files to Modify

```
src/ms_access_mcp/
├── adapters/
│   └── wincom.py          # Real export_form_to_text, export_report_to_text, export_all_versioning
├── services/
│   └── schema.py          # Add versioning methods
├── mcp/
│   └── server.py          # Add export tools
tests/unit/
├── test_versioning.py     # New tests
```

### Test Scenarios

1. **Export all** — database with 2 forms, 1 report, 3 modules, 1 macro → 7 files created
2. **Form not found** — export single form that doesn't exist → error
3. **Empty database** — no forms/reports/modules → `success: true, exported: {forms: [], ...}`
4. **Special chars in name** — form named `Test:Form` → file named `forms_Test_Form.txt`
5. **Module code correct** — verify exported module code matches `get_vba_code`

### What This Does NOT Do

- **Not** an import/version restore tool (that would be `import_form_from_text`)
- **Not** a migration tool
- **Not** encrypted VBA protection removal — just reads accessible code