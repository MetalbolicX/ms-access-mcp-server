// ComDbProps.res — Database properties + versioning operations
// Task 5.2 GREEN: dbprops + versioning
// Mirrors: src/ms_access_mcp/adapters/db_operations.py + versioning_io.py

// ---------------------------------------------------------------------------
// Types (must be declared in .res so they're in scope for type annotations)
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
  type_: string,
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
// Module-level helpers (internal — not exposed in .resi)
// ---------------------------------------------------------------------------

// _connected — true only when handles have a live Access app
let _connected: ComInterfaces.sessionHandles => bool = (
  (handles) => switch handles.accessApp {
    | Some(_) => true
    | None => false
  }
)

// _app — extract the winax COM object from handles (unsafe; caller must check _connected)
@val external _nullApp: 'a = "null"

let _app: ComInterfaces.sessionHandles => 'a = (
  (handles) => {
    switch handles.accessApp {
      | Some(app) => app
      | None => _nullApp
    }
  }
)

// ---------------------------------------------------------------------------
// DAO data-type constants (dbDataTypeEnum)
// https://learn.microsoft.com/en-us/office/client-developer/access/desktop-database-reference/datatypeenum
// ---------------------------------------------------------------------------

let daoTypeText: int = 10
let daoTypeLong: int = 4
let daoTypeBoolean: int = 1
let daoTypeDouble: int = 7
let daoTypeDate: int = 8
let daoTypeByte: int = 2

// ---------------------------------------------------------------------------
// DAO type helpers
// ---------------------------------------------------------------------------

// daoTypeFromString — maps type name string to DAO type integer
let daoTypeFromString: string => int = (
  (typeName) => {
    let lower = String.toLowerCase(typeName)
    switch lower {
      | "text" | "str" | "string" => daoTypeText
      | "long" | "int" | "integer" => daoTypeLong
      | "boolean" | "bool" => daoTypeBoolean
      | "double" | "float" => daoTypeDouble
      | "date" | "datetime" => daoTypeDate
      | "byte" => daoTypeByte
      | _ => daoTypeText
    }
  }
)

// detectDaoType — auto-detect best DAO type from a string value
// Precedence: Boolean → Long → Double → Text. Access accepts yes/no and -1
// as boolean values, while digit-only values remain Long for parity.
let detectDaoType: string => (string, int) = (
  (value) => {
    let lowered: string = String.toLowerCase(value)
    // Boolean
    if lowered == "true" || lowered == "false" || lowered == "yes" || lowered == "no" || value == "-1" {
      ("Boolean", daoTypeBoolean)
    } else {
      // Digit-only positive integer → Long
      let isDigitOnly = String.length(value) > 0 && {
        let digits = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
        let allDigits = Array.every(String.split(value, ""), (ch) =>
          Array.some(digits, (d) => d == ch)
        )
        allDigits
      }
      if isDigitOnly {
        ("Long", daoTypeLong)
      } else {
        // Try parse as float
        let parsed: option<float> = Float.fromString(value)
        switch parsed {
          | Some(_) => ("Double", daoTypeDouble)
          | None => ("Text", daoTypeText)
        }
      }
    }
  }
)

// ---------------------------------------------------------------------------
// Safe filename — strips \ / : * ? " < > |
// ---------------------------------------------------------------------------

// Uses TsBridge safeFilename helper
let safeFilename: string => string = (
  (name) => {
    Bindings.TsBridge.safeFilename(name)
  }
)

// ---------------------------------------------------------------------------
// SHA-256 helpers (using @noble/hashes)
// ---------------------------------------------------------------------------

type hashBytes

@module("@noble/hashes/utils.js")
external utf8ToBytes: string => hashBytes = "utf8ToBytes"

@module("@noble/hashes/sha2.js")
external sha256: hashBytes => hashBytes = "sha256"

@module("@noble/hashes/utils.js")
external bytesToHex: hashBytes => string = "bytesToHex"

let sha256Content: string => string = content =>
  content->utf8ToBytes->sha256->bytesToHex

// ---------------------------------------------------------------------------
// Internal: read a file as string (for dedup in exportAllVersioning)
// ---------------------------------------------------------------------------

let _readFileText: string => string = (
  (path) => {
    if NodeJs.Fs.existsSync(path) {
      let buf = NodeJs.Fs.readFileSync(path)
      NodeJs.Buffer.toStringWithEncoding(buf, NodeJs.StringEncoding.utf8)
    } else {
      ""
    }
  }
)

// ---------------------------------------------------------------------------
// Internal: write text to file
// ---------------------------------------------------------------------------

let _writeFileText: (string, string) => bool = (
  (path, content) => {
    try {
      let buf = NodeJs.Buffer.fromStringWithEncoding(content, NodeJs.StringEncoding.utf8)
      NodeJs.Fs.writeFileSync(path, buf)
      true
    } catch {
      | _ => false
    }
  }
)

// ---------------------------------------------------------------------------
// Internal: create directory (exist_ok)
// ---------------------------------------------------------------------------

let _mkdirp: string => bool = (
  (dir) => {
    try {
      NodeJs.Fs.mkdirSyncWith(dir, {recursive: true})
      true
    } catch {
      | _ => false
    }
  }
)

// ---------------------------------------------------------------------------
// Internal: check if file exists
// ---------------------------------------------------------------------------

let _fileExists: string => bool = (
  (path) => NodeJs.Fs.existsSync(path)
)

// ---------------------------------------------------------------------------
// Internal: Buffer <-> array<int> helpers (used by encode/decode/write/read)
// ponytail: array<int> is ReScript's universal byte sequence; Buffer<->array<int> is pure FFI.
// ---------------------------------------------------------------------------

@val external _bufferFromArray: array<int> => NodeJs.Buffer.t = "Buffer.from"
@val external _arrayFromBuffer: NodeJs.Buffer.t => array<int> = "Array.from"

// ---------------------------------------------------------------------------
// Internal: SHA256 of a file's content
// ---------------------------------------------------------------------------

// ponytail: file hashing uses node:crypto because @noble/hashes has no Buffer-specific overload.
// sha256Content (string path) already uses @noble/hashes; using node:crypto here is deliberate
// to keep the two hashing paths independent and avoid Buffer<->bytes coercion in this hot path.
@module("node:crypto")
external _randomBytes: int => NodeJs.Buffer.t = "randomBytes"

let _fileHash: string => string = (
  (path) => {
    // Uses TsBridge fileHash helper which uses ESM node:crypto
    Bindings.TsBridge.fileHash(path)
  }
)

// ---------------------------------------------------------------------------
// Internal: temp file for SaveAsText / LoadFromText
// ---------------------------------------------------------------------------

let _tempFile: (string, string) => string = (
  (prefix, suffix) => {
    let rnd = _randomBytes(8)->NodeJs.Buffer.toStringWithEncoding(NodeJs.StringEncoding.hex)
    NodeJs.Path.join2(NodeJs.Os.tmpdir(), prefix ++ rnd ++ suffix)
  }
)

// ---------------------------------------------------------------------------
// Internal: encode bytes for SaveAsText file (UTF-16LE+BOM or ANSI)
// Mirrors ComUi._encodeForSave
// ---------------------------------------------------------------------------

// ponytail: cp1252 encoding has no typed binding in NodeJS — raw unavoidable for acModule.
// Uses TsBridge codec helpers for encoding
let _encodeForSave: (int, string) => array<int> = (
  (objectType, textData) => {
    if objectType == 5 {
      // acModule — system ANSI, no BOM
      let enc = "windows-1252"  // Node.js name for cp1252
      Bindings.TsBridge.bytesFromString(textData, enc)
    } else {
      // Forms/reports/macros — UTF-16LE with BOM (typed Buffer.concat path)
      let bomBuf = NodeJs.Buffer.fromStringWithEncoding("\ufeff", NodeJs.StringEncoding.utf16le)
      let textBuf = NodeJs.Buffer.fromStringWithEncoding(textData, NodeJs.StringEncoding.utf16le)
      let combined = NodeJs.Buffer.concat([bomBuf, textBuf])
      _arrayFromBuffer(combined)
    }
  }
)

// ---------------------------------------------------------------------------
// Internal: decode bytes from LoadFromText file
// Mirrors ComUi._decodeFromLoad
// ---------------------------------------------------------------------------

// Uses TsBridge codec helpers for decoding
let _decodeFromLoad: (int, array<int>) => string = (
  (objectType, raw) => {
    if objectType == 5 {
      // acModule — system ANSI
      let enc = "windows-1252"
      Bindings.TsBridge.bytesToString(raw, enc)
    } else {
      // Forms/reports/macros — UTF-16LE with BOM
      let buf = _bufferFromArray(raw)
      let s = NodeJs.Buffer.toStringWithEncoding(buf, NodeJs.StringEncoding.utf16le)
      // Strip BOM
      switch String.get(s, 0) {
        | Some(c) if c == "\ufeff" => String.substring(s, ~start=1)
        | _ => s
      }
    }
  }
)

// ---------------------------------------------------------------------------
// Internal: write bytes to file (for LoadFromText temp file)
// ---------------------------------------------------------------------------

let _writeFileBytes: (string, array<int>) => bool = (
  (path, bytes) => {
    try {
      let buf = _bufferFromArray(bytes)
      NodeJs.Fs.writeFileSync(path, buf)
      true
    } catch {
      | _ => false
    }
  }
)

// ---------------------------------------------------------------------------
// Internal: read file as bytes
// ---------------------------------------------------------------------------

let _readFileBytes: string => array<int> = (
  (path) => {
    if NodeJs.Fs.existsSync(path) {
      let buf = NodeJs.Fs.readFileSync(path)
      _arrayFromBuffer(buf)
    } else {
      []
    }
  }
)

// ---------------------------------------------------------------------------
// Internal: delete file
// ---------------------------------------------------------------------------

let _unlinkFile: string => unit = (
  (path) => {
    try {
      NodeJs.Fs.unlinkSync(path)
    } catch {
      | _ => ()
    }
  }
)

// ---------------------------------------------------------------------------
// DAO property names sets (from db_operations.py)
// ---------------------------------------------------------------------------

// Startup category properties
let _STARTUP_PROP_NAMES: array<string> = [
  "apptitle", "startupform", "startupshowform", "allowfullmenus",
  "allowbuiltinpanels", "allowdefaultshortcutmenus", "allowshortcutmenus",
  "allowtoolbarchanges", "allowdesignchanges", "startmenubar", "startupmenubar",
  "startupshortcutmenubar", "startupshowstatusbar", "startupshowcontextmenus",
  "usesingledocumentinterface", "dontshowhelptext",
]

// App-level property names
let _APP_PROP_NAMES: array<string> = [
  "author", "company", "description", "keywords", "subject",
  "manager", "category", "comments", "hyperlinkbase", "appversion",
]

let _inSet: (string, array<string>) => bool = (
  (name, set) => {
    let lowered = String.toLowerCase(name)
    Array.some(set, (s) => s == lowered)
  }
)

// Internal prefixes to filter
let _INTERNAL_PREFIXES: array<string> = ["_", "MSys"]

let _isInternal: string => bool = (
  (name) => {
    switch String.get(name, 0) {
      | Some(c) => c == "_" || {
          let len = String.length(name)
          len >= 4 && String.substring(name, ~start=0, ~end=4) == "MSys"
        }
      | None => false
    }
  }
)

// ---------------------------------------------------------------------------
// getDatabaseProperties
// Reads CurrentDb.Properties and CurrentProject info.
// names: optional filter list (case-insensitive match).
// Returns {startup, app, project, all} dicts.
// ---------------------------------------------------------------------------

let getDatabaseProperties: (
  ComInterfaces.sessionHandles,
  option<array<string>>
) => Promise.t<propertyCategories> = (
  (handles, names) => {
    if !_connected(handles) {
      Promise.resolve({
        startup: Dict.make(),
        app: Dict.make(),
        project: Dict.make(),
        all: Dict.make(),
      })
    } else {
      let app = _app(handles)
      Bindings.JsCom.getDatabaseProperties(app, names)
        ->Promise.then(result => {
          // Convert the typed record fields to dicts
          let startup: dict<string> = Dict.make()
          let appDict: dict<string> = Dict.make()
          let projectDict: dict<string> = Dict.make()
          let allDict: dict<string> = Dict.make()

          // Copy result.startup to startup dict
          let startupKeys = Dict.keysToArray(result.startup)
          Array.reduce(startupKeys, (), (_, k) => {
            let v = Dict.get(result.startup, k)
            switch v {
              | Some(s) => Dict.set(startup, k, s)
              | None => ()
            }
            ()
          })

          // Copy result.app to appDict
          let appKeys = Dict.keysToArray(result.app)
          Array.reduce(appKeys, (), (_, k) => {
            let v = Dict.get(result.app, k)
            switch v {
              | Some(s) => Dict.set(appDict, k, s)
              | None => ()
            }
            ()
          })

          // Copy result.project to projectDict
          let projectKeys = Dict.keysToArray(result.project)
          Array.reduce(projectKeys, (), (_, k) => {
            let v = Dict.get(result.project, k)
            switch v {
              | Some(s) => Dict.set(projectDict, k, s)
              | None => ()
            }
            ()
          })

          // Copy result.all to allDict
          let allKeys = Dict.keysToArray(result.all)
          Array.reduce(allKeys, (), (_, k) => {
            let v = Dict.get(result.all, k)
            switch v {
              | Some(s) => Dict.set(allDict, k, s)
              | None => ()
            }
            ()
          })

           Promise.resolve({startup, app: appDict, project: projectDict, all: allDict})
         })
         ->Promise.catch(_ => Promise.resolve({
           startup: Dict.make(),
           app: Dict.make(),
           project: Dict.make(),
           all: Dict.make(),
         }))
    }
  }
)

// ---------------------------------------------------------------------------
// setDatabaseProperty — create or update a property on CurrentDb.Properties
// ---------------------------------------------------------------------------

let setDatabaseProperty: (
  ComInterfaces.sessionHandles,
  ~name: string,
  ~value: string,
  ~type_: option<string>
) => Promise.t<bool> = (
  (handles, ~name, ~value, ~type_) => {
    if !_connected(handles) {
      Promise.resolve(false)
    } else {
      let app = _app(handles)
      Bindings.JsCom.setDatabaseProperty(
        app,
        ~name,
        ~value,
        ~type_=switch type_ { | Some(t) => t | None => "" }
      )
        ->Promise.then(r => Promise.resolve(r == true))
        ->Promise.catch(_ => Promise.resolve(false))
    }
  }
)

// ---------------------------------------------------------------------------
// exportModuleToText — export VBA module code from VBE (in-memory, not SaveAsText)
// ---------------------------------------------------------------------------

let exportModuleToText: (ComInterfaces.sessionHandles, string) => Promise.t<string> = (
  (handles, moduleName) => {
    if !_connected(handles) {
      Promise.resolve("")
    } else {
      let app = _app(handles)
      Bindings.JsCom.exportModuleToText(app, moduleName)
        ->Promise.then(r => Promise.resolve(r))
        ->Promise.catch(_ => Promise.resolve(""))
    }
  }
)

// ---------------------------------------------------------------------------
// _tempSaveAsText — internal: use SaveAsText via COM, read temp file, return content
// ---------------------------------------------------------------------------

let _tempSaveAsText: (ComInterfaces.sessionHandles, int, string) => Promise.t<string> = (
  (handles, objectType, objectName) => {
    if !_connected(handles) { Promise.resolve("") }
    else {
      let app = _app(handles)
      Bindings.JsCom._tempSaveAsText(app, objectType, objectName)
        ->Promise.catch(_ => Promise.resolve(""))
    }
  }
)

// ---------------------------------------------------------------------------
// _tempLoadFromText — internal: write content to temp file, call LoadFromText
// ---------------------------------------------------------------------------

let _tempLoadFromText: (ComInterfaces.sessionHandles, int, string, string) => Promise.t<bool> = (
  (handles, objectType, objectName, textData) => {
    if !_connected(handles) { Promise.resolve(false) }
    else {
      let app = _app(handles)
      Bindings.JsCom._tempLoadFromText(app, objectType, objectName, textData)
        ->Promise.catch(_ => Promise.resolve(false))
    }
  }
)

// ---------------------------------------------------------------------------
// exportMacroToText — export macro via SaveAsText(acMacro=8)
// ---------------------------------------------------------------------------

let exportMacroToText: (ComInterfaces.sessionHandles, string) => Promise.t<string> = (
  (handles, macroName) => _tempSaveAsText(handles, 8, macroName)
)

// ---------------------------------------------------------------------------
// importMacroFromText — import macro via LoadFromText(acMacro=8)
// ---------------------------------------------------------------------------

let importMacroFromText: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool> = (
  (handles, macroName, textData) => _tempLoadFromText(handles, 8, macroName, textData)
)

// ---------------------------------------------------------------------------
// exportQueryToText — export query via SaveAsText(acQuery=5)
// ---------------------------------------------------------------------------

let exportQueryToText: (ComInterfaces.sessionHandles, string) => Promise.t<string> = (
  (handles, queryName) => _tempSaveAsText(handles, 5, queryName)
)

// ---------------------------------------------------------------------------
// importQueryFromText — import query via LoadFromText(acQuery=5)
// ---------------------------------------------------------------------------

let importQueryFromText: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool> = (
  (handles, queryName, textData) => _tempLoadFromText(handles, 5, queryName, textData)
)

// ---------------------------------------------------------------------------
// exportAllVersioning — export all forms/reports/modules/macros/queries
// with SHA-256 deduplication
// ---------------------------------------------------------------------------

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
) => Promise.t<versioningExportResult> = (
  (handles, ~outputDir, ~dedup, ~moduleExt, ~getFormsFn, ~getReportsFn, ~getModulesFn, ~getMacrosFn, ~getQueriesFn, ~exportFormToTextFn, ~exportReportToTextFn) => {
    if !_connected(handles) {
      Promise.resolve({
        success: false,
        exported: {forms: [], reports: [], modules: [], macros: [], queries: []},
        outputDir,
        fileCount: 0,
      })
    } else {
      // Helper: write content to path, return SHA256 of content, bool (skipped)
      let _exportOne: (string, string, int, string, string, bool) => Promise.t<(bool, string, bool)> = (
        (outDir, safeName, objectType, objName, prefix, skipDup) => {
          _tempSaveAsText(handles, objectType, objName)
            ->Promise.then(content => {
              if content == "" {
                Promise.resolve((false, "", false))
              } else {
                let h = sha256Content(content)
                let outPath = outDir ++ "/" ++ prefix ++ "_" ++ safeName ++ ".txt"
                let skipped = skipDup && _fileExists(outPath) && {
                  let existingHash = _fileHash(outPath)
                  existingHash == h
                }
                if !skipped {
                  let _ = _writeFileText(outPath, content)
                  ()
                }
                Promise.resolve((true, h, skipped))
              }
            })
            ->Promise.catch(_ => Promise.resolve((false, "", false)))
        }
      )

      // Create subdirs
      let formsDir = outputDir ++ "/forms"
      let reportsDir = outputDir ++ "/reports"
      let modulesDir = outputDir ++ "/modules"
      let macrosDir = outputDir ++ "/macros"
      let queriesDir = outputDir ++ "/queries"

      let _ = _mkdirp(formsDir)
      let _ = _mkdirp(reportsDir)
      let _ = _mkdirp(modulesDir)
      let _ = _mkdirp(macrosDir)
      let _ = _mkdirp(queriesDir)

      let exportedForms: array<string> = []
      let exportedReports: array<string> = []
      let exportedModules: array<string> = []
      let exportedMacros: array<string> = []
      let exportedQueries: array<string> = []

      // Export forms
      getFormsFn()
        ->Promise.then(forms => {
          Array.reduce(forms, Promise.resolve(), (p, form) => {
            p->Promise.then(() => {
              let safeName = safeFilename(form.name)
              let outPath = formsDir ++ "/" ++ "forms_" ++ safeName ++ ".txt"
              exportFormToTextFn(form.name)
                ->Promise.then(content => {
                  if content == "" { Promise.resolve() }
                  else {
                    let h = sha256Content(content)
                    let skipped = dedup && _fileExists(outPath) && _fileHash(outPath) == h
                    if !skipped {
                      let _ = _writeFileText(outPath, content)
                      ()
                    }
                    if !skipped { Array.push(exportedForms, form.name) }
                    Promise.resolve()
                  }
                })
                ->Promise.catch(_ => Promise.resolve())
            })
          })
          ->Promise.then(() => {
            // Export reports
            getReportsFn()
              ->Promise.then(reports => {
                Array.reduce(reports, Promise.resolve(), (p, report) => {
                  p->Promise.then(() => {
                    let safeName = safeFilename(report.name)
                    let outPath = reportsDir ++ "/" ++ "reports_" ++ safeName ++ ".txt"
                    exportReportToTextFn(report.name)
                      ->Promise.then(content => {
                        if content == "" { Promise.resolve() }
                        else {
                          let h = sha256Content(content)
                          let skipped = dedup && _fileExists(outPath) && _fileHash(outPath) == h
                          if !skipped {
                            let _ = _writeFileText(outPath, content)
                            ()
                          }
                          if !skipped { Array.push(exportedReports, report.name) }
                          Promise.resolve()
                        }
                      })
                      ->Promise.catch(_ => Promise.resolve())
                  })
                })
                ->Promise.then(() => {
                  // Export modules (in-memory code, not SaveAsText)
                  getModulesFn()
                    ->Promise.then(modules => {
                      Array.reduce(modules, Promise.resolve(), (p, mod) => {
                        p->Promise.then(() => {
                          let safeName = safeFilename(mod.name)
                          let outPath = modulesDir ++ "/" ++ "modules_" ++ safeName ++ moduleExt
                          let content = mod.code
                          let h = sha256Content(content)
                          let skipped = dedup && _fileExists(outPath) && _fileHash(outPath) == h
                          if !skipped {
                            let _ = _writeFileText(outPath, content)
                            ()
                          }
                          if !skipped { Array.push(exportedModules, mod.name) }
                          Promise.resolve()
                        })
                      })
                      ->Promise.then(() => {
                        // Export macros
                        getMacrosFn()
                          ->Promise.then(macros => {
                            Array.reduce(macros, Promise.resolve(), (p, macro) => {
                              p->Promise.then(() => {
                                let safeName = safeFilename(macro.name)
                                let outPath = macrosDir ++ "/" ++ "macros_" ++ safeName ++ ".txt"
                                // Macro content is static (just the name header)
                                let content = "Macro: " ++ macro.name ++ "\nType: Access Macro\n"
                                let h = sha256Content(content)
                                let skipped = dedup && _fileExists(outPath) && _fileHash(outPath) == h
                                if !skipped {
                                  let _ = _writeFileText(outPath, content)
                                  ()
                                }
                                if !skipped { Array.push(exportedMacros, macro.name) }
                                Promise.resolve()
                              })
                            })
                            ->Promise.then(() => {
                              // Export queries
                              getQueriesFn()
                                ->Promise.then(queries => {
                                  Array.reduce(queries, Promise.resolve(), (p, query) => {
                                    p->Promise.then(() => {
                                      let safeName = safeFilename(query.name)
                                      let outPath = queriesDir ++ "/" ++ "queries_" ++ safeName ++ ".txt"
                                      exportQueryToText(handles, query.name)
                                        ->Promise.then(content => {
                                          if content == "" { Promise.resolve() }
                                          else {
                                            let h = sha256Content(content)
                                            let skipped = dedup && _fileExists(outPath) && _fileHash(outPath) == h
                                            if !skipped {
                                              let _ = _writeFileText(outPath, content)
                                              ()
                                            }
                                            if !skipped { Array.push(exportedQueries, query.name) }
                                            Promise.resolve()
                                          }
                                        })
                                        ->Promise.catch(_ => Promise.resolve())
                                    })
                                  })
                                  ->Promise.then(() => {
                                    let total = Array.length(exportedForms)
                                      + Array.length(exportedReports)
                                      + Array.length(exportedModules)
                                      + Array.length(exportedMacros)
                                      + Array.length(exportedQueries)
                                    Promise.resolve({
                                      success: true,
                                      exported: {
                                        forms: exportedForms,
                                        reports: exportedReports,
                                        modules: exportedModules,
                                        macros: exportedMacros,
                                        queries: exportedQueries,
                                      },
                                      outputDir,
                                      fileCount: total,
                                    })
                                  })
                                })
                            })
                          })
                      })
                    })
                })
              })
          })
        })
        ->Promise.catch(_ => Promise.resolve({
          success: false,
          exported: {forms: [], reports: [], modules: [], macros: [], queries: []},
          outputDir,
          fileCount: 0,
        }))
    }
  }
)

// ---------------------------------------------------------------------------
// compareVersioning — compare DB objects against exported files
// ---------------------------------------------------------------------------

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
) => Promise.t<versioningCompareResult> = (
  (handles, ~exportDir, ~getFormsFn, ~getReportsFn, ~getModulesFn, ~getMacrosFn, ~getQueriesFn, ~exportFormToTextFn, ~exportReportToTextFn, ~exportMacroToTextFn, ~exportQueryToTextFn, ~exportModuleToTextFn) => {
    let _ = exportModuleToTextFn
    if !_connected(handles) {
      Promise.resolve({new: [], missing: [], changed: [], unchanged: []})
    } else {
      // Subdirs: forms, reports, modules, macros, queries
      // Read exported files: prefix_name.txt → original name
      let new: array<versioningEntry> = []
      let missing: array<versioningEntry> = []
      let changed: array<versioningEntry> = []
      let unchanged: array<versioningEntry> = []

      // Helper to extract name from filename: type_name.txt → name
      let _extractName: string => string = (
        (fname) => {
          let idx = String.indexOf(fname, "_")
          let lastDot = String.lastIndexOf(fname, ".")
          if idx >= 0 && lastDot > idx {
            String.substring(fname, ~start=idx + 1, ~end=lastDot)
          } else {
            ""
          }
        }
      )

      // Helper to list files in a directory
      let _listDirFiles: string => array<string> = (
        (dir) => {
          if NodeJs.Fs.existsSync(dir) {
            let all = NodeJs.Fs.readdirSync(dir)
            Array.filter(all, (f) => f->String.endsWith(".txt") || f->String.endsWith(".bas"))
          } else {
            []
          }
        }
      )

      // Compare forms
      getFormsFn()
        ->Promise.then(forms => {
          let dirPath = exportDir ++ "/forms"
          let exportedFiles: dict<string> = Dict.make()
          let files = _listDirFiles(dirPath)
          Array.reduce(files, (), (_, fname) => {
            let cleanName = _extractName(fname)
            if cleanName != "" { Dict.set(exportedFiles, safeFilename(cleanName), fname) }
            ()
          })
          Array.reduce(forms, Promise.resolve(), (p, form) => {
            p->Promise.then(() => {
              let sfn = safeFilename(form.name)
              switch Dict.get(exportedFiles, sfn) {
                | Some(fname) => {
                    let filePath = dirPath ++ "/" ++ fname
                    let fileContent = _readFileText(filePath)
                    exportFormToTextFn(form.name)
                      ->Promise.then(dbContent => {
                        if dbContent == fileContent {
                          Array.push(unchanged, {type_: "forms", name: form.name})
                        } else {
                          Array.push(changed, {type_: "forms", name: form.name})
                        }
                        Promise.resolve()
                      })
                      ->Promise.catch(_ => {
                        Array.push(changed, {type_: "forms", name: form.name})
                        Promise.resolve()
                      })
                  }
                | None => {
                    Array.push(new, {type_: "forms", name: form.name})
                    Promise.resolve()
                  }
              }
            })
          })
          ->Promise.then(() => {
            let keys = Dict.keysToArray(exportedFiles)
            Array.reduce(keys, Promise.resolve(), (p, safeKey) => {
              p->Promise.then(() => {
                let found = Array.some(forms, (f) => safeFilename(f.name) == safeKey)
                if !found {
                  let fname = switch Dict.get(exportedFiles, safeKey) { | Some(f) => f | None => "" }
                  let nameExtracted = _extractName(fname)
                  Array.push(missing, {type_: "forms", name: nameExtracted})
                }
                Promise.resolve()
              })
            })
          })
        })
        ->Promise.then(() =>
          // Compare reports
          getReportsFn()
            ->Promise.then(reports => {
              let dirPath = exportDir ++ "/reports"
              let exportedFiles: dict<string> = Dict.make()
              let files = _listDirFiles(dirPath)
              Array.reduce(files, (), (_, fname) => {
                let cleanName = _extractName(fname)
                if cleanName != "" { Dict.set(exportedFiles, safeFilename(cleanName), fname) }
                ()
              })
              Array.reduce(reports, Promise.resolve(), (p, report) => {
                p->Promise.then(() => {
                  let sfn = safeFilename(report.name)
                  switch Dict.get(exportedFiles, sfn) {
                    | Some(fname) => {
                        let filePath = dirPath ++ "/" ++ fname
                        let fileContent = _readFileText(filePath)
                        exportReportToTextFn(report.name)
                          ->Promise.then(dbContent => {
                            if dbContent == fileContent {
                              Array.push(unchanged, {type_: "reports", name: report.name})
                            } else {
                              Array.push(changed, {type_: "reports", name: report.name})
                            }
                            Promise.resolve()
                          })
                          ->Promise.catch(_ => {
                            Array.push(changed, {type_: "reports", name: report.name})
                            Promise.resolve()
                          })
                      }
                    | None => {
                        Array.push(new, {type_: "reports", name: report.name})
                        Promise.resolve()
                      }
                  }
                })
              })
              ->Promise.then(() => {
                let keys = Dict.keysToArray(exportedFiles)
                Array.reduce(keys, Promise.resolve(), (p, safeKey) => {
                  p->Promise.then(() => {
                    let found = Array.some(reports, (r) => safeFilename(r.name) == safeKey)
                    if !found {
                      let fname = switch Dict.get(exportedFiles, safeKey) { | Some(f) => f | None => "" }
                      let nameExtracted = _extractName(fname)
                      Array.push(missing, {type_: "reports", name: nameExtracted})
                    }
                    Promise.resolve()
                  })
                })
              })
            })
        )
        ->Promise.then(() =>
          // Compare modules
          getModulesFn()
            ->Promise.then(modules => {
              let dirPath = exportDir ++ "/modules"
              let exportedFiles: dict<string> = Dict.make()
              let files = _listDirFiles(dirPath)
              Array.reduce(files, (), (_, fname) => {
                let cleanName = _extractName(fname)
                if cleanName != "" { Dict.set(exportedFiles, safeFilename(cleanName), fname) }
                ()
              })
              Array.reduce(modules, Promise.resolve(), (p, mod) => {
                p->Promise.then(() => {
                  let sfn = safeFilename(mod.name)
                  switch Dict.get(exportedFiles, sfn) {
                    | Some(fname) => {
                        let filePath = dirPath ++ "/" ++ fname
                        let fileContent = _readFileText(filePath)
                        if fileContent == mod.code {
                          Array.push(unchanged, {type_: "modules", name: mod.name})
                        } else {
                          Array.push(changed, {type_: "modules", name: mod.name})
                        }
                        Promise.resolve()
                      }
                    | None => {
                        Array.push(new, {type_: "modules", name: mod.name})
                        Promise.resolve()
                      }
                  }
                })
              })
              ->Promise.then(() => {
                let keys = Dict.keysToArray(exportedFiles)
                Array.reduce(keys, Promise.resolve(), (p, safeKey) => {
                  p->Promise.then(() => {
                    let found = Array.some(modules, (m) => safeFilename(m.name) == safeKey)
                    if !found {
                      Array.push(missing, {type_: "modules", name: safeKey})
                    }
                    Promise.resolve()
                  })
                })
              })
            })
        )
        ->Promise.then(() =>
          // Compare macros
          getMacrosFn()
            ->Promise.then(macros => {
              let dirPath = exportDir ++ "/macros"
              let exportedFiles: dict<string> = Dict.make()
              let files = _listDirFiles(dirPath)
              Array.reduce(files, (), (_, fname) => {
                let cleanName = _extractName(fname)
                if cleanName != "" { Dict.set(exportedFiles, safeFilename(cleanName), fname) }
                ()
              })
              Array.reduce(macros, Promise.resolve(), (p, macro) => {
                p->Promise.then(() => {
                  let sfn = safeFilename(macro.name)
                  switch Dict.get(exportedFiles, sfn) {
                    | Some(fname) => {
                        let filePath = dirPath ++ "/" ++ fname
                        let fileContent = _readFileText(filePath)
                        exportMacroToTextFn(macro.name)
                          ->Promise.then(dbContent => {
                            if dbContent == fileContent {
                              Array.push(unchanged, {type_: "macros", name: macro.name})
                            } else {
                              Array.push(changed, {type_: "macros", name: macro.name})
                            }
                            Promise.resolve()
                          })
                          ->Promise.catch(_ => {
                            Array.push(changed, {type_: "macros", name: macro.name})
                            Promise.resolve()
                          })
                      }
                    | None => {
                        Array.push(new, {type_: "macros", name: macro.name})
                        Promise.resolve()
                      }
                  }
                })
              })
              ->Promise.then(() => {
                let keys = Dict.keysToArray(exportedFiles)
                Array.reduce(keys, Promise.resolve(), (p, safeKey) => {
                  p->Promise.then(() => {
                    let found = Array.some(macros, (m) => safeFilename(m.name) == safeKey)
                    if !found {
                      let fname = switch Dict.get(exportedFiles, safeKey) { | Some(f) => f | None => "" }
                      let nameExtracted = _extractName(fname)
                      Array.push(missing, {type_: "macros", name: nameExtracted})
                    }
                    Promise.resolve()
                  })
                })
              })
            })
        )
        ->Promise.then(() =>
          // Compare queries
          getQueriesFn()
            ->Promise.then(queries => {
              let dirPath = exportDir ++ "/queries"
              let exportedFiles: dict<string> = Dict.make()
              let files = _listDirFiles(dirPath)
              Array.reduce(files, (), (_, fname) => {
                let cleanName = _extractName(fname)
                if cleanName != "" { Dict.set(exportedFiles, safeFilename(cleanName), fname) }
                ()
              })
              Array.reduce(queries, Promise.resolve(), (p, query) => {
                p->Promise.then(() => {
                  let sfn = safeFilename(query.name)
                  switch Dict.get(exportedFiles, sfn) {
                    | Some(fname) => {
                        let filePath = dirPath ++ "/" ++ fname
                        let fileContent = _readFileText(filePath)
                        exportQueryToTextFn(query.name)
                          ->Promise.then(dbContent => {
                            if dbContent == fileContent {
                              Array.push(unchanged, {type_: "queries", name: query.name})
                            } else {
                              Array.push(changed, {type_: "queries", name: query.name})
                            }
                            Promise.resolve()
                          })
                          ->Promise.catch(_ => {
                            Array.push(changed, {type_: "queries", name: query.name})
                            Promise.resolve()
                          })
                      }
                    | None => {
                        Array.push(new, {type_: "queries", name: query.name})
                        Promise.resolve()
                      }
                  }
                })
              })
              ->Promise.then(() => {
                let keys = Dict.keysToArray(exportedFiles)
                Array.reduce(keys, Promise.resolve(), (p, safeKey) => {
                  p->Promise.then(() => {
                    let found = Array.some(queries, (q) => safeFilename(q.name) == safeKey)
                    if !found {
                      let fname = switch Dict.get(exportedFiles, safeKey) { | Some(f) => f | None => "" }
                      let nameExtracted = _extractName(fname)
                      Array.push(missing, {type_: "queries", name: nameExtracted})
                    }
                    Promise.resolve()
                  })
                })
              })
            })
        )
        ->Promise.then(() =>
          Promise.resolve({new, missing, changed, unchanged})
        )
        ->Promise.catch(_ => Promise.resolve({new, missing, changed, unchanged}))
    }
  }
)

// ---------------------------------------------------------------------------
// importAllVersioning — import from export directory
// Files sorted by name for deterministic ordering.
// ---------------------------------------------------------------------------

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
) => Promise.t<versioningImportResult> = (
  (handles, ~inputDir, ~getModulesFn, ~setVbaCodeFn, ~compileVbaFn, ~importFormFromTextFn, ~importReportFromTextFn, ~importMacroFromTextFn, ~importQueryFromTextFn) => {
    if !_connected(handles) {
      Promise.resolve({success: false, error: Some("Not connected to database"), imported: {forms: [], reports: [], modules: [], macros: [], queries: []}, errors: None})
    } else {
      // Read file with BOM detection (UTF-16-LE or UTF-8)
      // ponytail: BOM check needs byte-level inspection — no typed Buffer indexing in NodeJS bindings.
      // utf16le-with-BOM files are written by SaveAsText; utf8 files are user-created.
      let _safeRead: string => string = (
        (path) => {
          if NodeJs.Fs.existsSync(path) {
            let buf = NodeJs.Fs.readFileSync(path)
            let content = NodeJs.Buffer.toStringWithEncoding(buf, NodeJs.StringEncoding.utf8)
            // Strip UTF-16LE BOM if present (0xFF 0xFE in the raw buffer = '\ufeff' in utf8 decode of a UTF-16LE file)
            switch String.get(content, 0) {
              | Some(c) if c == "\ufeff" => String.substring(content, ~start=1)
              | _ => content
            }
          } else {
            ""
          }
        }
      )

      // List files in a subdir with prefix filter
      let _listFiles: (string, string, string, string) => array<(string, string)> = (
        (baseDir, typeKey, ext1, ext2) => {
          let dirPath = baseDir ++ "/" ++ typeKey
          let files = if NodeJs.Fs.existsSync(dirPath) {
            let all = NodeJs.Fs.readdirSync(dirPath)
            Array.filter(all, (f) => {
              let prefix = typeKey ++ "_"
              f->String.startsWith(prefix) && (f->String.endsWith(ext1) || f->String.endsWith(ext2))
            })
          } else {
            []
          }
          // Sort for deterministic order (lexicographic, matching JS Array.sort behavior)
          let sorted: array<string> = Array.toSorted(Array.copy(files), String.compare)
          Array.map(sorted, (fname) => {
            // Extract name: typeKey_name.ext → name
            let idx = String.indexOf(fname, "_")
            let name = if idx >= 0 { String.substring(fname, ~start=idx + 1) } else { fname }
            // Uses TsBridge cleanName helper
            let cleanName = Bindings.TsBridge.cleanName(name)
            (cleanName, dirPath ++ "/" ++ fname)
          })
        }
      )

      let importedForms: array<string> = []
      let importedReports: array<string> = []
      let importedModules: array<string> = []
      let importedMacros: array<string> = []
      let importedQueries: array<string> = []
      let errors: array<string> = []

      // Import modules first (VBA must exist before forms/reports)
      getModulesFn()
        ->Promise.then(_existingModules => {
          let moduleFiles = _listFiles(inputDir, "modules", ".bas", ".txt")
          Array.reduce(moduleFiles, Promise.resolve(), (p, (name, path)) => {
            p->Promise.then(() => {
              let data = _safeRead(path)
              setVbaCodeFn(name, data)
                ->Promise.then(ok => {
  if ok { Array.push(importedModules, name) }
  else { Array.push(errors, "module " ++ name ++ ": set_vba_code failed") }
                  Promise.resolve()
                })
                  ->Promise.catch(_ => {
                    Array.push(errors, "module " ++ name ++ ": set_vba_code failed")
                    Promise.resolve()
                  })
            })
          })
          ->Promise.then(() => compileVbaFn())
          ->Promise.then(_compileResult => {
            if !_compileResult.success {
              Array.push(errors, "VBA compile error after module import")
            }
            Promise.resolve()
          })
          ->Promise.then(() => {
            // Import forms
            let formFiles = _listFiles(inputDir, "forms", ".txt", ".txt")
            Array.reduce(formFiles, Promise.resolve(), (p, (name, path)) => {
              p->Promise.then(() => {
                let data = _safeRead(path)
                importFormFromTextFn(name, data)
                  ->Promise.then(ok => {
                    if ok { Array.push(importedForms, name) }
                    else { Array.push(errors, "form " ++ name ++ ": import failed") }
                    Promise.resolve()
                  })
                  ->Promise.catch(_ => {
                    Array.push(errors, "form " ++ name ++ ": import failed")
                    Promise.resolve()
                  })
              })
            })
            ->Promise.then(() => {
              // Import reports
              let reportFiles = _listFiles(inputDir, "reports", ".txt", ".txt")
              Array.reduce(reportFiles, Promise.resolve(), (p, (name, path)) => {
                p->Promise.then(() => {
                  let data = _safeRead(path)
                  importReportFromTextFn(name, data)
                    ->Promise.then(ok => {
                      if ok { Array.push(importedReports, name) }
                      else { Array.push(errors, "report " ++ name ++ ": import failed") }
                      Promise.resolve()
                    })
                    ->Promise.catch(_ => {
                      Array.push(errors, "report " ++ name ++ ": import failed")
                      Promise.resolve()
                    })
                })
              })
              ->Promise.then(() => {
                // Import macros
                let macroFiles = _listFiles(inputDir, "macros", ".txt", ".txt")
                Array.reduce(macroFiles, Promise.resolve(), (p, (name, path)) => {
                  p->Promise.then(() => {
                    let data = _safeRead(path)
                    importMacroFromTextFn(name, data)
                      ->Promise.then(ok => {
                        if ok { Array.push(importedMacros, name) }
                        else { Array.push(errors, "macro " ++ name ++ ": import failed") }
                        Promise.resolve()
                      })
                      ->Promise.catch(_ => {
                        Array.push(errors, "macro " ++ name ++ ": import failed")
                        Promise.resolve()
                      })
                  })
                })
                ->Promise.then(() => {
                  // Import queries
                  let queryFiles = _listFiles(inputDir, "queries", ".txt", ".txt")
                  Array.reduce(queryFiles, Promise.resolve(), (p, (name, path)) => {
                    p->Promise.then(() => {
                      let data = _safeRead(path)
                      importQueryFromTextFn(name, data)
                        ->Promise.then(ok => {
                          if ok { Array.push(importedQueries, name) }
                          else { Array.push(errors, "query " ++ name ++ ": import failed") }
                          Promise.resolve()
                        })
                        ->Promise.catch(_ => {
                          Array.push(errors, "query " ++ name ++ ": import failed")
                          Promise.resolve()
                        })
                    })
                  })
                  ->Promise.then(() => {
                    Promise.resolve({
                      success: Array.length(errors) == 0,
                      error: if Array.length(errors) > 0 { Some(Array.join(errors, "; ")) } else { None },
                      imported: {
                        forms: importedForms,
                        reports: importedReports,
                        modules: importedModules,
                        macros: importedMacros,
                        queries: importedQueries,
                      },
                      errors: if Array.length(errors) > 0 { Some(errors) } else { None },
                    })
                  })
                })
              })
            })
          })
        })
        ->Promise.catch(_ => Promise.resolve({
          success: false,
          error: Some("import_all_versioning failed"),
          imported: {forms: [], reports: [], modules: [], macros: [], queries: []},
          errors: None,
        }))
    }
  }
)

// ---------------------------------------------------------------------------
// exportSchemaDdl — export table schemas as DDL SQL files
// ---------------------------------------------------------------------------

let exportSchemaDdl: (
  ComInterfaces.sessionHandles,
  ~outputDir: string,
  ~getTablesFn: unit => Promise.t<array<tableInfo>>,
  ~getRelationshipsFn: unit => Promise.t<array<relationshipInfo>>,
) => Promise.t<schemaDdlResult> = (
  (handles, ~outputDir, ~getTablesFn, ~getRelationshipsFn) => {
    if !_connected(handles) {
      Promise.resolve({success: false, error: Some("Not connected"), ddlTables: "", ddlRelationships: "", tablesExported: 0, relationshipsExported: 0})
    } else {
      let schemaDir = outputDir ++ "/schema"
      let _ = _mkdirp(schemaDir)
      let ddlTablesPath = schemaDir ++ "/ddl_tables.sql"
      let ddlRelsPath = schemaDir ++ "/ddl_relationships.sql"

      getTablesFn()
        ->Promise.then(tables => {
          // Build DDL tables SQL
          let tableDdl = Array.map(tables, (table) => {
            let colDefs = Array.map(table.fields, (field) => {
              let nullable = if field.required { " NOT NULL" } else { " NULL" }
              "  [" ++ field.name ++ "] " ++ field.type_ ++ nullable
            })
            "CREATE TABLE [" ++ table.name ++ "] (\n" ++ Array.join(colDefs, ",\n") ++ "\n);\n"
          })->Array.join("\n")


          let tablesHeader = "-- Access Table DDL\n-- Generated by ms-access-mcp-server\n\n"
          let _ = _writeFileText(ddlTablesPath, tablesHeader ++ tableDdl)
          Promise.resolve(tables)
        })
        ->Promise.then(tables => {
          getRelationshipsFn()
            ->Promise.then(rels => {
              let relDdl = Array.map(rels, (rel) => {
                "-- Relationship: " ++ rel.name ++ "\n" ++
                "-- Table: " ++ rel.table ++ ", Foreign Table: " ++ rel.foreignTable ++ "\n" ++
                "-- Attributes: " ++ rel.attributes ++ "\n" ++
                "ALTER TABLE [" ++ rel.table ++ "] ADD CONSTRAINT [" ++ rel.name ++ "] " ++
                "FOREIGN KEY REFERENCES [" ++ rel.foreignTable ++ "];\n"
              })->Array.join("\n")

              let relsHeader = "-- Access Relationship DDL\n-- Generated by ms-access-mcp-server\n\n"
              let _ = _writeFileText(ddlRelsPath, relsHeader ++ relDdl)
              Promise.resolve({
                success: true,
                error: None,
                ddlTables: ddlTablesPath,
                ddlRelationships: ddlRelsPath,
                tablesExported: Array.length(tables),
                relationshipsExported: Array.length(rels),
              })
            })
        })
        ->Promise.catch(_ => Promise.resolve({
          success: false,
          error: Some("export_schema_ddl failed"),
          ddlTables: "",
          ddlRelationships: "",
          tablesExported: 0,
          relationshipsExported: 0,
        }))
    }
  }
)
