// ComVba.resi — VBA module CRUD + Application.Run
// Mirrors src/ms_access_mcp/adapters/vba_operations.py
// Non-fatal: all operations return false/empty on failure (no raw exn escapes).
// These types are used by tests; actual ComVba uses WINAX_BINDING directly.

// vbProcedureInfo — mirrors vba_operations.vba_list_procedures output
type vbProcedureInfo = {
  name: string,
  procType: string,  // "Sub" | "Function" | "Property"
  startLine: int,
  lineCount: int,
}

// compileResult — mirrors vba_operations.compile_vba() dict
type compileResult = {
  success: bool,
  error: option<string>,
}

// moduleInfo — mirrors Python models.database.ModuleInfo
type moduleInfo = {
  name: string,
  moduleType: string,  // "Standard Module" | "Class Module"
  code: string,
}

// saveResult — mirrors vba_operations.save_database() dict
type saveResult = {
  success: bool,
  savedModules: int,
  errors: array<string>,
}
