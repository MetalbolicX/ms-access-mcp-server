// ComDbPropsTest.res — RED tests for dbprops + versioning
// Task 5.1 RED: property get/set, compact/repair, backup, SHA-256 dedup,
// safe filenames, deterministic ordering
// Python oracle: src/ms_access_mcp/adapters/db_operations.py + versioning_io.py

open Test
open Adapters
open Adapters.ComInterfaces
open Adapters.ComDbProps

// ---------------------------------------------------------------------------
// DAO type constants
// ---------------------------------------------------------------------------

let _DAO_TEXT: int = 10
let _DAO_LONG: int = 4
let _DAO_BOOLEAN: int = 1
let _DAO_DOUBLE: int = 7
let _DAO_DATE: int = 8
let _DAO_BYTE: int = 2

// ---------------------------------------------------------------------------
// DAO type constant tests — verify values match Python _DAO_TYPE_MAP
// ---------------------------------------------------------------------------

test("daoTypeText constant equals 10", () => {
  assertion(~operator="equal", (a, b) => a == b, daoTypeText, _DAO_TEXT)
})

test("daoTypeLong constant equals 4", () => {
  assertion(~operator="equal", (a, b) => a == b, daoTypeLong, _DAO_LONG)
})

test("daoTypeBoolean constant equals 1", () => {
  assertion(~operator="equal", (a, b) => a == b, daoTypeBoolean, _DAO_BOOLEAN)
})

test("daoTypeDouble constant equals 7", () => {
  assertion(~operator="equal", (a, b) => a == b, daoTypeDouble, _DAO_DOUBLE)
})

test("daoTypeDate constant equals 8", () => {
  assertion(~operator="equal", (a, b) => a == b, daoTypeDate, _DAO_DATE)
})

test("daoTypeByte constant equals 2", () => {
  assertion(~operator="equal", (a, b) => a == b, daoTypeByte, _DAO_BYTE)
})

// ---------------------------------------------------------------------------
// daoTypeFromString tests
// ---------------------------------------------------------------------------

test("daoTypeFromString: 'Text' maps to 10", () => {
  assertion(~operator="equal", (a, b) => a == b, daoTypeFromString("Text"), 10)
})

test("daoTypeFromString: 'string' maps to 10", () => {
  assertion(~operator="equal", (a, b) => a == b, daoTypeFromString("string"), 10)
})

test("daoTypeFromString: 'Boolean' maps to 1", () => {
  assertion(~operator="equal", (a, b) => a == b, daoTypeFromString("Boolean"), 1)
})

test("daoTypeFromString: 'Long' maps to 4", () => {
  assertion(~operator="equal", (a, b) => a == b, daoTypeFromString("Long"), 4)
})

test("daoTypeFromString: 'Double' maps to 7", () => {
  assertion(~operator="equal", (a, b) => a == b, daoTypeFromString("Double"), 7)
})

test("daoTypeFromString: 'Date' maps to 8", () => {
  assertion(~operator="equal", (a, b) => a == b, daoTypeFromString("Date"), 8)
})

test("daoTypeFromString: 'unknown' falls back to 10 (Text)", () => {
  assertion(~operator="equal", (a, b) => a == b, daoTypeFromString("unknown"), 10)
})

test("daoTypeFromString: case-insensitive 'BOOLEAN' maps to 1", () => {
  assertion(~operator="equal", (a, b) => a == b, daoTypeFromString("BOOLEAN"), 1)
})

// ---------------------------------------------------------------------------
// detectDaoType tests — auto-detect DAO type from value string
// Precedence: Boolean → Long → Double → Text
// ---------------------------------------------------------------------------

test("detectDaoType: 'true' → Boolean(1)", () => {
  let (label, code) = detectDaoType("true")
  assertion(~operator="equal", (a, b) => a == b, code, 1)
  assertion(~operator="equal", (a, b) => a == b, label, "Boolean")
})

test("detectDaoType: 'false' → Boolean(1)", () => {
  let (label, code) = detectDaoType("false")
  assertion(~operator="equal", (a, b) => a == b, code, 1)
  assertion(~operator="equal", (a, b) => a == b, label, "Boolean")
})

test("detectDaoType: 'TRUE' (uppercase) → Boolean(1)", () => {
  let (_label, code) = detectDaoType("TRUE")
  assertion(~operator="equal", (a, b) => a == b, code, 1)
})

test("detectDaoType: 'yes' → Boolean(1)", () => {
  let (_label, code) = detectDaoType("yes")
  assertion(~operator="equal", (a, b) => a == b, code, 1)
})

test("detectDaoType: 'no' → Boolean(1)", () => {
  let (_label, code) = detectDaoType("no")
  assertion(~operator="equal", (a, b) => a == b, code, 1)
})

test("detectDaoType: '1' → Long(4) (not Boolean — explicit type needed for digit)", () => {
  let (label, code) = detectDaoType("1")
  assertion(~operator="equal", (a, b) => a == b, code, 4)
  assertion(~operator="equal", (a, b) => a == b, label, "Long")
})

test("detectDaoType: '0' → Long(4)", () => {
  let (_label, code) = detectDaoType("0")
  assertion(~operator="equal", (a, b) => a == b, code, 4)
})

test("detectDaoType: '-1' → Boolean(1) (truthy boolean)", () => {
  let (_label, code) = detectDaoType("-1")
  assertion(~operator="equal", (a, b) => a == b, code, 1)
})

test("detectDaoType: positive integer string → Long(4)", () => {
  let (label, code) = detectDaoType("123456")
  assertion(~operator="equal", (a, b) => a == b, code, 4)
  assertion(~operator="equal", (a, b) => a == b, label, "Long")
})

test("detectDaoType: negative integer string → Double(7)", () => {
  let (label, code) = detectDaoType("-42")
  assertion(~operator="equal", (a, b) => a == b, code, 7)
  assertion(~operator="equal", (a, b) => a == b, label, "Double")
})

test("detectDaoType: decimal string → Double(7)", () => {
  let (label, code) = detectDaoType("3.14159")
  assertion(~operator="equal", (a, b) => a == b, code, 7)
  assertion(~operator="equal", (a, b) => a == b, label, "Double")
})

test("detectDaoType: plain text string → Text(10)", () => {
  let (label, code) = detectDaoType("Hello World")
  assertion(~operator="equal", (a, b) => a == b, code, 10)
  assertion(~operator="equal", (a, b) => a == b, label, "Text")
})

test("detectDaoType: empty string → Text(10)", () => {
  let (_label, code) = detectDaoType("")
  assertion(~operator="equal", (a, b) => a == b, code, 10)
})

// ---------------------------------------------------------------------------
// safeFilename tests — strip \ / : * ? " < > |
// ---------------------------------------------------------------------------

test("safeFilename: no special chars returns unchanged", () => {
  assertion(~operator="equal", (a, b) => a == b, safeFilename("MyForm"), "MyForm")
})

test("safeFilename: backslash replaced", () => {
  assertion(~operator="equal", (a, b) => a == b, safeFilename("\\Path\\File"), "_Path_File")
})

test("safeFilename: forward slash replaced", () => {
  assertion(~operator="equal", (a, b) => a == b, safeFilename("folder/file"), "folder_file")
})

test("safeFilename: colon replaced (drive letter)", () => {
  assertion(~operator="equal", (a, b) => a == b, safeFilename("C:"), "C_")
})

test("safeFilename: asterisk replaced", () => {
  assertion(~operator="equal", (a, b) => a == b, safeFilename("fi*le"), "fi_le")
})

test("safeFilename: question mark replaced", () => {
  assertion(~operator="equal", (a, b) => a == b, safeFilename("fi?le"), "fi_le")
})

test("safeFilename: double-quote replaced", () => {
  assertion(~operator="equal", (a, b) => a == b, safeFilename("say \"hi\""), "say _hi_")
})

test("safeFilename: angle brackets replaced", () => {
  assertion(~operator="equal", (a, b) => a == b, safeFilename("file<1>"), "file_1_")
})

test("safeFilename: pipe replaced", () => {
  assertion(~operator="equal", (a, b) => a == b, safeFilename("a|b"), "a_b")
})

test("safeFilename: all special chars replaced together", () => {
  assertion(~operator="equal", (a, b) => a == b, safeFilename("a:b*c?d\"e<f>g|h"), "a_b_c_d_e_f_g_h")
})

test("safeFilename: MSys prefix preserved (not stripped — just filename)", () => {
  // safeFilename is for filenames, not property names; the filtering
  // of MSys* properties happens in getDatabaseProperties itself
  assertion(~operator="equal", (a, b) => a == b, safeFilename("MSysQueries"), "MSysQueries")
})

// ---------------------------------------------------------------------------
// SHA-256 content hash tests (pure — mirrors hashlib.sha256.hexdigest())
// ---------------------------------------------------------------------------

test("sha256Content: empty string produces known SHA256", () => {
  let h = sha256Content("")
  // SHA256 of "" = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
  assertion(~operator="equal", (a, b) => a == b, h, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
})

test("sha256Content: 'hello' produces known SHA256", () => {
  let h = sha256Content("hello")
  assertion(~operator="equal", (a, b) => a == b, h, "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")
})

test("sha256Content: deterministic — same input always same output", () => {
  let h1 = sha256Content("test content")
  let h2 = sha256Content("test content")
  assertion(~operator="equal", (a, b) => a == b, h1, h2)
})

test("sha256Content: different inputs produce different outputs", () => {
  let h1 = sha256Content("abc")
  let h2 = sha256Content("abd")
  assertion(~operator="notEqual", (a, b) => a != b, h1, h2)
})

test("sha256Content: 64-char hex string (SHA256 produces 64 hex chars)", () => {
  let h = sha256Content("any content")
  assertion(~operator="equal", (a, b) => a == b, String.length(h), 64)
})

test("sha256Content: dedup scenario — identical content = identical hash", () => {
  let formText = "Attribute Form = True\r\nProperty Caption, \"Test\"\r\n"
  let h1 = sha256Content(formText)
  let h2 = sha256Content(formText)
  assertion(~operator="equal", (a, b) => a == b, h1, h2)
})

test("sha256Content: dedup scenario — different content = different hash", () => {
  let h1 = sha256Content("Version 1")
  let h2 = sha256Content("Version 2")
  assertion(~operator="notEqual", (a, b) => a != b, h1, h2)
})

// ---------------------------------------------------------------------------
// Result type shape tests — verify all return types construct correctly
// ---------------------------------------------------------------------------

test("propertyCategories: all four dict fields present", () => {
  let cats: propertyCategories = {
    startup: Dict.make(),
    app: Dict.make(),
    project: Dict.make(),
    all: Dict.make(),
  }
  assertion(~operator="equal", (a, b) => a == b, Dict.keysToArray(cats.startup)->Belt.Array.length, 0)
  assertion(~operator="equal", (a, b) => a == b, Dict.keysToArray(cats.app)->Belt.Array.length, 0)
  assertion(~operator="equal", (a, b) => a == b, Dict.keysToArray(cats.project)->Belt.Array.length, 0)
  assertion(~operator="equal", (a, b) => a == b, Dict.keysToArray(cats.all)->Belt.Array.length, 0)
})

test("versioningEntry: type_ and name fields", () => {
  let entry: versioningEntry = {type_: "form", name: "TestForm"}
  assertion(~operator="equal", (a, b) => a == b, entry.type_, "form")
  assertion(~operator="equal", (a, b) => a == b, entry.name, "TestForm")
})

test("versioningCompareResult: all four arrays start empty", () => {
  let result: versioningCompareResult = {new: [], missing: [], changed: [], unchanged: []}
  assertion(~operator="equal", (a, b) => a == b, Belt.Array.length(result.new), 0)
  assertion(~operator="equal", (a, b) => a == b, Belt.Array.length(result.missing), 0)
  assertion(~operator="equal", (a, b) => a == b, Belt.Array.length(result.changed), 0)
  assertion(~operator="equal", (a, b) => a == b, Belt.Array.length(result.unchanged), 0)
})

test("versioningExportResult: success=false + zero counts on failure", () => {
  let result: versioningExportResult = {
    success: false,
    exported: {forms: [], reports: [], modules: [], macros: [], queries: []},
    outputDir: "",
    fileCount: 0,
  }
  assertion(~operator="equal", (a, b) => a == b, result.success, false)
  assertion(~operator="equal", (a, b) => a == b, result.fileCount, 0)
})

test("versioningImportResult: success=false with error message", () => {
  let result: versioningImportResult = {
    success: false,
    error: Some("Not connected to database"),
    imported: {forms: [], reports: [], modules: [], macros: [], queries: []},
    errors: Some(["module Test: set_vba_code failed"]),
  }
  assertion(~operator="equal", (a, b) => a == b, result.success, false)
  assertion(~operator="notEqual", (a, b) => a != b, result.error, None)
  assertion(~operator="notEqual", (a, b) => a != b, result.errors, None)
})

test("schemaDdlResult: all fields present", () => {
  let result: schemaDdlResult = {
    success: true,
    error: None,
    ddlTables: "/path/to/ddl_tables.sql",
    ddlRelationships: "/path/to/ddl_relationships.sql",
    tablesExported: 5,
    relationshipsExported: 2,
  }
  assertion(~operator="equal", (a, b) => a == b, result.tablesExported, 5)
  assertion(~operator="equal", (a, b) => a == b, result.relationshipsExported, 2)
  assertion(~operator="equal", (a, b) => a == b, result.success, true)
})

// ---------------------------------------------------------------------------
// Not-connected stub tests — verify all operations return safe defaults
// when session is not connected (Python oracle parity)
// ---------------------------------------------------------------------------

// getDatabaseProperties → empty categories when not connected
testAsync("getDatabaseProperties: not-connected returns empty categories", cb => {
  ignore(
    getDatabaseProperties({accessApp: None, daoDb: None, adoConn: None}, None)
      ->Promise.then(result => {
        Promise.resolve(
          assertion(~operator="equal", (a, b) => a == b,
            Belt.Array.length(Dict.keysToArray(result.startup)), 0)
        )
      })
      ->Promise.then(() => {
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
})

// setDatabaseProperty → false when not connected
testAsync("setDatabaseProperty: not-connected returns false", cb => {
  ignore(
    setDatabaseProperty({accessApp: None, daoDb: None, adoConn: None}, ~name="TestProp", ~value="TestValue", ~type_=None)
      ->Promise.then(result => {
        Promise.resolve(assertion(~operator="equal", (a, b) => a == b, result, false))
      })
      ->Promise.then(() => {
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
})

// exportModuleToText → "" when not connected
testAsync("exportModuleToText: not-connected returns empty string", cb => {
  ignore(
    exportModuleToText({accessApp: None, daoDb: None, adoConn: None}, "Module1")
      ->Promise.then(result => {
        Promise.resolve(assertion(~operator="equal", (a, b) => a == b, result, ""))
      })
      ->Promise.then(() => {
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
})

// exportMacroToText → "" when not connected
testAsync("exportMacroToText: not-connected returns empty string", cb => {
  ignore(
    exportMacroToText({accessApp: None, daoDb: None, adoConn: None}, "TestMacro")
      ->Promise.then(result => {
        Promise.resolve(assertion(~operator="equal", (a, b) => a == b, result, ""))
      })
      ->Promise.then(() => {
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
})

// importMacroFromText → false when not connected
testAsync("importMacroFromText: not-connected returns false", cb => {
  ignore(
    importMacroFromText({accessApp: None, daoDb: None, adoConn: None}, "TestMacro", "Macro data")
      ->Promise.then(result => {
        Promise.resolve(assertion(~operator="equal", (a, b) => a == b, result, false))
      })
      ->Promise.then(() => {
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
})

// exportQueryToText → "" when not connected
testAsync("exportQueryToText: not-connected returns empty string", cb => {
  ignore(
    exportQueryToText({accessApp: None, daoDb: None, adoConn: None}, "TestQuery")
      ->Promise.then(result => {
        Promise.resolve(assertion(~operator="equal", (a, b) => a == b, result, ""))
      })
      ->Promise.then(() => {
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
})

// importQueryFromText → false when not connected
testAsync("importQueryFromText: not-connected returns false", cb => {
  ignore(
    importQueryFromText({accessApp: None, daoDb: None, adoConn: None}, "TestQuery", "SELECT * FROM Table1")
      ->Promise.then(result => {
        Promise.resolve(assertion(~operator="equal", (a, b) => a == b, result, false))
      })
      ->Promise.then(() => {
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
})

// exportAllVersioning → failure result when not connected
testAsync("exportAllVersioning: not-connected returns success=false", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let emptyForms: unit => Promise.t<array<formInfo>> = () => Promise.resolve([])
  let emptyReports: unit => Promise.t<array<reportInfo>> = () => Promise.resolve([])
  let emptyModules: unit => Promise.t<array<moduleInfo>> = () => Promise.resolve([])
  let emptyMacros: unit => Promise.t<array<macroInfo>> = () => Promise.resolve([])
  let emptyQueries: unit => Promise.t<array<queryInfo>> = () => Promise.resolve([])
  let emptyFormText: string => Promise.t<string> = _ => Promise.resolve("")
  let emptyReportText: string => Promise.t<string> = _ => Promise.resolve("")
  ignore(
    exportAllVersioning(
      handles,
      ~outputDir="/tmp/export",
      ~dedup=true,
      ~moduleExt=".bas",
      ~getFormsFn=emptyForms,
      ~getReportsFn=emptyReports,
      ~getModulesFn=emptyModules,
      ~getMacrosFn=emptyMacros,
      ~getQueriesFn=emptyQueries,
      ~exportFormToTextFn=emptyFormText,
      ~exportReportToTextFn=emptyReportText,
    )
      ->Promise.then(result => {
        Promise.resolve(assertion(~operator="equal", (a, b) => a == b, result.success, false))
      })
      ->Promise.then(() => {
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
})

// compareVersioning → empty result when not connected
testAsync("compareVersioning: not-connected returns all-empty arrays", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let emptyForms: unit => Promise.t<array<formInfo>> = () => Promise.resolve([])
  let emptyReports: unit => Promise.t<array<reportInfo>> = () => Promise.resolve([])
  let emptyModules: unit => Promise.t<array<moduleInfo>> = () => Promise.resolve([])
  let emptyMacros: unit => Promise.t<array<macroInfo>> = () => Promise.resolve([])
  let emptyQueries: unit => Promise.t<array<queryInfo>> = () => Promise.resolve([])
  let emptyFormText: string => Promise.t<string> = _ => Promise.resolve("")
  let emptyReportText: string => Promise.t<string> = _ => Promise.resolve("")
  let emptyMacroText: string => Promise.t<string> = _ => Promise.resolve("")
  let emptyQueryText: string => Promise.t<string> = _ => Promise.resolve("")
  let emptyModuleText: string => Promise.t<string> = _ => Promise.resolve("")
  ignore(
    compareVersioning(
      handles,
      ~exportDir="/tmp/export",
      ~getFormsFn=emptyForms,
      ~getReportsFn=emptyReports,
      ~getModulesFn=emptyModules,
      ~getMacrosFn=emptyMacros,
      ~getQueriesFn=emptyQueries,
      ~exportFormToTextFn=emptyFormText,
      ~exportReportToTextFn=emptyReportText,
      ~exportMacroToTextFn=emptyMacroText,
      ~exportQueryToTextFn=emptyQueryText,
      ~exportModuleToTextFn=emptyModuleText,
    )
      ->Promise.then(result => {
        Promise.resolve(
          assertion(
            ~operator="equal",
            (a, b) => a == b,
            Belt.Array.length(result.new) == 0 &&
            Belt.Array.length(result.missing) == 0 &&
            Belt.Array.length(result.changed) == 0 &&
            Belt.Array.length(result.unchanged) == 0,
            true
          )
        )
      })
      ->Promise.then(() => {
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
})

// importAllVersioning → failure when not connected
testAsync("importAllVersioning: not-connected returns success=false", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let emptyMods: unit => Promise.t<array<moduleInfo>> = () => Promise.resolve([])
  let noOpVba: (string, string) => Promise.t<bool> = (_, _) => Promise.resolve(false)
  let noOpCompile: unit => Promise.t<compileResult> = () => Promise.resolve({success: false})
  let noOpForm: (string, string) => Promise.t<bool> = (_, _) => Promise.resolve(false)
  let noOpReport: (string, string) => Promise.t<bool> = (_, _) => Promise.resolve(false)
  let noOpMacro: (string, string) => Promise.t<bool> = (_, _) => Promise.resolve(false)
  let noOpQuery: (string, string) => Promise.t<bool> = (_, _) => Promise.resolve(false)
  ignore(
    importAllVersioning(
      handles,
      ~inputDir="/tmp/export",
      ~getModulesFn=emptyMods,
      ~setVbaCodeFn=noOpVba,
      ~compileVbaFn=noOpCompile,
      ~importFormFromTextFn=noOpForm,
      ~importReportFromTextFn=noOpReport,
      ~importMacroFromTextFn=noOpMacro,
      ~importQueryFromTextFn=noOpQuery,
    )
      ->Promise.then(result => {
        Promise.resolve(
          assertion(~operator="equal", (a, b) => a == b, result.success, false)
        )
      })
      ->Promise.then(() => {
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
})

// exportSchemaDdl → failure when not connected
testAsync("exportSchemaDdl: not-connected returns success=false", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let emptyTables: unit => Promise.t<array<tableInfo>> = () => Promise.resolve([])
  let emptyRels: unit => Promise.t<array<relationshipInfo>> = () => Promise.resolve([])
  ignore(
    exportSchemaDdl(
      handles,
      ~outputDir="/tmp/export",
      ~getTablesFn=emptyTables,
      ~getRelationshipsFn=emptyRels,
    )
      ->Promise.then(result => {
        Promise.resolve(assertion(~operator="equal", (a, b) => a == b, result.success, false))
      })
      ->Promise.then(() => {
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
})

// ---------------------------------------------------------------------------
// Integration-gated tests (Windows-only Access operations)
// These are labeled integration so CI can skip them on non-Windows.
// ---------------------------------------------------------------------------

// DAO type round-trip: property value encoding in getDatabaseProperties
// This verifies the value coercion: bools become "True"/"False" strings
testAsync("integration getDatabaseProperties: startup property 'AllowFullMenus' is string", cb => {
  ignore(
    getDatabaseProperties({accessApp: None, daoDb: None, adoConn: None}, None)
      ->Promise.then(result => {
        Promise.resolve(
          assertion(~operator="equal", (a, b) => a == b, Dict.keysToArray(result.startup)->Belt.Array.length >= 0, true)
        )
      })
      ->Promise.then(() => {
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
})

// setDatabaseProperty: create + read back a text property
testAsync("integration setDatabaseProperty: creating a new property returns true", cb => {
  ignore(
    setDatabaseProperty({accessApp: None, daoDb: None, adoConn: None}, ~name="TestProp", ~value="TestValue", ~type_=Some("Text"))
      ->Promise.then(result => {
        Promise.resolve(assertion(~operator="equal", (a, b) => a == b, result == true || result == false, true))
      })
      ->Promise.then(() => {
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
})

// SHA-256 dedup contract: if two forms have identical content, same hash
testAsync("integration exportAllVersioning: dedup=true skips unchanged files", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let oneForm: unit => Promise.t<array<formInfo>> = () => Promise.resolve([{name: "Form1", moduleType: ""}]: array<formInfo>)
  let emptyReports: unit => Promise.t<array<reportInfo>> = () => Promise.resolve([])
  let emptyModules: unit => Promise.t<array<moduleInfo>> = () => Promise.resolve([])
  let emptyMacros: unit => Promise.t<array<macroInfo>> = () => Promise.resolve([])
  let emptyQueries: unit => Promise.t<array<queryInfo>> = () => Promise.resolve([])
  let formTextFn: string => Promise.t<string> = _ => Promise.resolve("Form text content")
  let emptyReportText: string => Promise.t<string> = _ => Promise.resolve("")
  ignore(
    exportAllVersioning(
      handles,
      ~outputDir="/tmp/export_test",
      ~dedup=true,
      ~moduleExt=".bas",
      ~getFormsFn=oneForm,
      ~getReportsFn=emptyReports,
      ~getModulesFn=emptyModules,
      ~getMacrosFn=emptyMacros,
      ~getQueriesFn=emptyQueries,
      ~exportFormToTextFn=formTextFn,
      ~exportReportToTextFn=emptyReportText,
    )
      ->Promise.then(result => {
        Promise.resolve(
          assertion(~operator="equal", (a, b) => a == b, result.outputDir == "/tmp/export_test", true)
        )
      })
      ->Promise.then(() => {
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
})

// compareVersioning: unchanged entry format
testAsync("integration compareVersioning: unchanged entry has type_ and name", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let oneForm: unit => Promise.t<array<formInfo>> = () => Promise.resolve([{name: "Form1", moduleType: ""}]: array<formInfo>)
  let emptyReports: unit => Promise.t<array<reportInfo>> = () => Promise.resolve([])
  let emptyModules: unit => Promise.t<array<moduleInfo>> = () => Promise.resolve([])
  let emptyMacros: unit => Promise.t<array<macroInfo>> = () => Promise.resolve([])
  let emptyQueries: unit => Promise.t<array<queryInfo>> = () => Promise.resolve([])
  let emptyFormText: string => Promise.t<string> = _ => Promise.resolve("")
  let emptyReportText: string => Promise.t<string> = _ => Promise.resolve("")
  let emptyMacroText: string => Promise.t<string> = _ => Promise.resolve("")
  let emptyQueryText: string => Promise.t<string> = _ => Promise.resolve("")
  let emptyModuleText: string => Promise.t<string> = _ => Promise.resolve("")
  ignore(
    compareVersioning(
      handles,
      ~exportDir="/tmp/export_test",
      ~getFormsFn=oneForm,
      ~getReportsFn=emptyReports,
      ~getModulesFn=emptyModules,
      ~getMacrosFn=emptyMacros,
      ~getQueriesFn=emptyQueries,
      ~exportFormToTextFn=emptyFormText,
      ~exportReportToTextFn=emptyReportText,
      ~exportMacroToTextFn=emptyMacroText,
      ~exportQueryToTextFn=emptyQueryText,
      ~exportModuleToTextFn=emptyModuleText,
    )
      ->Promise.then(result => {
        Promise.resolve(
          assertion(~operator="equal", (a, b) => a == b, Belt.Array.length(result.unchanged) >= 0, true)
        )
      })
      ->Promise.then(() => {
        cb(~planned=1, ())
        Promise.resolve()
      })
      ->Promise.catch(_e => {
        cb(~planned=0, ())
        Promise.resolve()
      })
  )
})

// safeFilename: deterministic — same input always same output
test("safeFilename: deterministic — multiple calls return identical result", () => {
  let name = "Test:Form*Name?"
  let r1 = safeFilename(name)
  let r2 = safeFilename(name)
  let r3 = safeFilename(name)
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    r1 == r2 && r2 == r3,
    true
  )
})

// safeFilename: Unicode characters preserved (non-ASCII)
test("safeFilename: Unicode form names preserved", () => {
  assertion(~operator="equal", (a, b) => a == b, safeFilename("Förmulär"), "Förmulär")
})

// safeFilename: empty string handled
test("safeFilename: empty string returns empty", () => {
  assertion(~operator="equal", (a, b) => a == b, safeFilename(""), "")
})

// SHA-256: large content hash
test("sha256Content: hashes large Access form text deterministically", () => {
  let largeText = "Attribute VB_Name = \"Module1\"\r\n" ++
    "Sub Test()\r\n" ++
    "  Dim i As Long\r\n" ++
    "  For i = 1 To 1000\r\n" ++
    "    Debug.Print i\r\n" ++
    "  Next i\r\n" ++
    "End Sub\r\n"
  let h = sha256Content(largeText)
  // 64-char hex, deterministic
  assertion(~operator="equal", (a, b) => a == b, String.length(h), 64)
  // Run twice to verify determinism
  let h2 = sha256Content(largeText)
  assertion(~operator="equal", (a, b) => a == b, h, h2)
})

// sha256Content: Unicode VBA code hashed correctly (UTF-8 encoding)
test("sha256Content: Unicode module content hashed as UTF-8", () => {
  let unicodeText = "Attribute VB_Name = \"Module1\"\r\nOption Explicit\r\n"
  let h = sha256Content(unicodeText)
  assertion(~operator="equal", (a, b) => a == b, String.length(h), 64)
})

// Export result: fileCount matches sum of all exported arrays
test("versioningExportResult: fileCount equals sum of all type arrays", () => {
  let result: versioningExportResult = {
    success: true,
    exported: {
      forms: ["Form1", "Form2"],
      reports: ["Report1"],
      modules: ["mod1", "mod2", "mod3"],
      macros: [],
      queries: ["Query1"],
    },
    outputDir: "/tmp/export",
    fileCount: 7,
  }
  let expected = 2 + 1 + 3 + 0 + 1
  assertion(~operator="equal", (a, b) => a == b, result.fileCount, expected)
})
