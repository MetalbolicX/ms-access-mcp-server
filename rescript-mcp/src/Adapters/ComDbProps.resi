// ComDbProps.resi — Interface for database properties and versioning operations
// Task 5.2 GREEN: dbprops + versioning in ComDbProps.res
// Mirrors: src/ms_access_mcp/adapters/db_operations.py + versioning_io.py

// ---------------------------------------------------------------------------
// DAO data-type constants (dbDataTypeEnum)
// ---------------------------------------------------------------------------

let daoTypeText: int      // 10 — string/variant
let daoTypeLong: int       // 4  — 32-bit integer
let daoTypeBoolean: int    // 1  — boolean
let daoTypeDouble: int     // 7  — IEEE 64-bit float
let daoTypeDate: int       // 8  — date/time
let daoTypeByte: int       // 2  — unsigned byte

// ---------------------------------------------------------------------------
// DAO type helpers (mirrors _DAO_TYPE_MAP + _detect_dao_type from db_operations.py)
// ---------------------------------------------------------------------------

let daoTypeFromString: string => int
let detectDaoType: string => (string, int)

// ---------------------------------------------------------------------------
// Safe filename (mirrors safe_filename from versioning_io.py)
// Strips: \ / : * ? " < > |
// ---------------------------------------------------------------------------

let safeFilename: string => string

// ---------------------------------------------------------------------------
// SHA-256 hash helpers (mirrors hashlib.sha256 in versioning_io.py)
// ---------------------------------------------------------------------------

let sha256Content: string => string   // SHA256 of a string (UTF-8 encoded)

// ---------------------------------------------------------------------------
// Named types for anonymous record shapes used in function signatures
// ---------------------------------------------------------------------------

type formInfo = {
  name: string,
  moduleType: string,
}

type reportInfo = {
  name: string,
  moduleType: string,
}

type moduleInfo = {
  name: string,
  code: string,
}

type macroInfo = {
  name: string,
}

type queryInfo = {
  name: string,
}

type tableFieldInfo = {
  name: string,
  type_: string,   // column data type (renamed from 'type' — 'type' is a ReScript keyword)
  required: bool,
}

type tableInfo = {
  name: string,
  fields: array<tableFieldInfo>,
}

type relationshipInfo = {
  name: string,
  table: string,
  foreignTable: string,
  attributes: string,
}

type exportedVersioningObjects = {
  forms: array<string>,
  reports: array<string>,
  modules: array<string>,
  macros: array<string>,
  queries: array<string>,
}

type importedVersioningObjects = {
  forms: array<string>,
  reports: array<string>,
  modules: array<string>,
  macros: array<string>,
  queries: array<string>,
}

type compileResult = {
  success: bool,
}

// ---------------------------------------------------------------------------
// Result types
// ---------------------------------------------------------------------------

type propertyCategories = {
  startup: dict<string>,
  app: dict<string>,
  project: dict<string>,
  all: dict<string>,
}

type versioningEntry = {
  type_: string,
  name: string,
}

type versioningCompareResult = {
  new: array<versioningEntry>,
  missing: array<versioningEntry>,
  changed: array<versioningEntry>,
  unchanged: array<versioningEntry>,
}

type versioningExportResult = {
  success: bool,
  exported: exportedVersioningObjects,
  outputDir: string,
  fileCount: int,
}

type versioningImportResult = {
  success: bool,
  error: option<string>,
  imported: importedVersioningObjects,
  errors: option<array<string>>,
}

type schemaDdlResult = {
  success: bool,
  error: option<string>,
  ddlTables: string,
  ddlRelationships: string,
  tablesExported: int,
  relationshipsExported: int,
}

// ---------------------------------------------------------------------------
// Database property operations
// ---------------------------------------------------------------------------

let getDatabaseProperties: (
  ComInterfaces.sessionHandles,
  option<array<string>>
) => Promise.t<propertyCategories>
// Returns {startup, app, project, all} dicts; all keys lowercased for lookup.
// Internal properties (_* and MSys*) are filtered out.
// Project info comes from CurrentProject.FullName/Name/ProjectType.

let setDatabaseProperty: (
  ComInterfaces.sessionHandles,
  ~name: string,
  ~value: string,
  ~type_: option<string>
) => Promise.t<bool>
// Creates or updates a property on CurrentDb.Properties.
// type_: "Text" | "Long" | "Boolean" | "Double" | "Date" | "Byte" | None (auto-detect).
// Auto-detect precedence: Boolean → Long → Double → Text.
// Returns true on success, false on any error.

// ---------------------------------------------------------------------------
// Versioning export / import / compare (mirrors versioning_io.py)
// ---------------------------------------------------------------------------

// Export VBA module code as plain text (in-memory, not SaveAsText)
let exportModuleToText: (ComInterfaces.sessionHandles, string) => Promise.t<string>

// Export / import macros via SaveAsText(acMacro=8)
let exportMacroToText: (ComInterfaces.sessionHandles, string) => Promise.t<string>
let importMacroFromText: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool>

// Export / import queries via SaveAsText(acQuery=5)
let exportQueryToText: (ComInterfaces.sessionHandles, string) => Promise.t<string>
let importQueryFromText: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool>

// Export all versioning objects (forms/reports/modules/macros/queries)
// dedup=true: skip files whose SHA256 matches the existing file content
let exportAllVersioning: (
  ComInterfaces.sessionHandles,
  ~outputDir: string,
  ~dedup: bool,
  ~moduleExt: string,
  ~getFormsFn: unit => Promise.t<array<formInfo>>,
  ~getReportsFn: unit => Promise.t<array<reportInfo>>,
  ~getModulesFn: unit => Promise.t<array<moduleInfo>>,
  ~getMacrosFn: unit => Promise.t<array<macroInfo>>,
  ~getQueriesFn: unit => Promise.t<array<queryInfo>>,
  ~exportFormToTextFn: string => Promise.t<string>,
  ~exportReportToTextFn: string => Promise.t<string>,
) => Promise.t<versioningExportResult>

// Compare DB objects against exported files
let compareVersioning: (
  ComInterfaces.sessionHandles,
  ~exportDir: string,
  ~getFormsFn: unit => Promise.t<array<formInfo>>,
  ~getReportsFn: unit => Promise.t<array<reportInfo>>,
  ~getModulesFn: unit => Promise.t<array<moduleInfo>>,
  ~getMacrosFn: unit => Promise.t<array<macroInfo>>,
  ~getQueriesFn: unit => Promise.t<array<queryInfo>>,
  ~exportFormToTextFn: string => Promise.t<string>,
  ~exportReportToTextFn: string => Promise.t<string>,
  ~exportMacroToTextFn: string => Promise.t<string>,
  ~exportQueryToTextFn: string => Promise.t<string>,
  ~exportModuleToTextFn: string => Promise.t<string>,
) => Promise.t<versioningCompareResult>
// Returns {new, missing, changed, unchanged} — each entry has type_ and name.

let importAllVersioning: (
  ComInterfaces.sessionHandles,
  ~inputDir: string,
  ~getModulesFn: unit => Promise.t<array<moduleInfo>>,
  ~setVbaCodeFn: (string, string) => Promise.t<bool>,
  ~compileVbaFn: unit => Promise.t<compileResult>,
  ~importFormFromTextFn: (string, string) => Promise.t<bool>,
  ~importReportFromTextFn: (string, string) => Promise.t<bool>,
  ~importMacroFromTextFn: (string, string) => Promise.t<bool>,
  ~importQueryFromTextFn: (string, string) => Promise.t<bool>,
) => Promise.t<versioningImportResult>
// Import ordering: modules → forms → reports → macros → queries.
// Files sorted by name for deterministic order (deterministic ordering requirement).

let exportSchemaDdl: (
  ComInterfaces.sessionHandles,
  ~outputDir: string,
  ~getTablesFn: unit => Promise.t<array<tableInfo>>,
  ~getRelationshipsFn: unit => Promise.t<array<relationshipInfo>>,
) => Promise.t<schemaDdlResult>
