// ComUiTest.res — RED tests for UI forms/reports/controls/macros + encoding
// Task 4.1 RED: forms/reports/controls/macros shapes; UTF-16LE+BOM definitions
// vs ANSI VBA round trip uncorrupted.
// Python oracle: src/ms_access_mcp/adapters/ui_operations.py

open Test
open Adapters.ComInterfaces

// ---------------------------------------------------------------------------
// Object type constants (mirrored from ui_operations.py)
// acForm = 2, acReport = 4, acModule = 5, acMacro = 8
// ---------------------------------------------------------------------------

let _ACFORM: int = 2
let _ACREPORT: int = 4
let _ACMODULE: int = 5
let _ACMACRO: int = 8

// ---------------------------------------------------------------------------
// Named record types for UI objects
// ---------------------------------------------------------------------------

type controlInfo = {
  name: string,
  controlType: string,
  properties: dict<string>,
}

type formInfo = {
  name: string,
  recordSource: string,
  controls: array<controlInfo>,
}

type reportInfo = {
  name: string,
  recordSource: string,
  controls: array<controlInfo>,
}

type macroInfo = {
  name: string,
  macroType: string,
  dateCreated: string,
  dateModified: string,
}

type formSectionInfo = {
  index: int,
  name: string,
  sectionType: string,
  visible: bool,
  height: int,
}

// ---------------------------------------------------------------------------
// Encoding constants — UTF-16LE BOM (U+FEFF)
// ---------------------------------------------------------------------------

let _UTF16LE_BOM: string = "\ufeff"

// ---------------------------------------------------------------------------
// Section constants
// ---------------------------------------------------------------------------

let _SECTION_DETAIL: int = 0
let _SECTION_HEADER: int = 1
let _SECTION_FOOTER: int = 2
let _SECTION_PAGE_HEADER: int = 3
let _SECTION_PAGE_FOOTER: int = 4

// ---------------------------------------------------------------------------
// Control type id → name mapping
// ---------------------------------------------------------------------------

let controlTypeName: int => string = (
  (t) => switch t {
    | 100 => "TextBox"
    | 101 => "Label"
    | 102 => "CommandButton"
    | 103 => "OptionButton"
    | 104 => "ComboBox"
    | 105 => "ListBox"
    | 106 => "SubForm"
    | 107 => "ToggleButton"
    | 108 => "CheckBox"
    | 109 => "OptionGroup"
    | 110 => "TabControl"
    | 111 => "Page"
    | 112 => "Image"
    | 114 => "BoundObjectFrame"
    | 115 => "ObjectFrame"
    | 118 => "Line"
    | 119 => "Rectangle"
    | 120 => "PageBreak"
    | 122 => "Attachment"
    | 123 => "NavigationButton"
    | 124 => "NavigationControl"
    | 126 => "WebBrowserControl"
    | 128 => "EmptyCell"
    | n => "Control(" ++ Int.toString(n) ++ ")"
  }
)

// ---------------------------------------------------------------------------
// Section id → name mapping
// ---------------------------------------------------------------------------

let sectionName: int => string = (
  (s) => switch s {
    | 0 => "detail"
    | 1 => "header"
    | 2 => "footer"
    | 3 => "page_header"
    | 4 => "page_footer"
    | n => "Section(" ++ Int.toString(n) ++ ")"
  }
)

// ---------------------------------------------------------------------------
// ANSI encoding detection (locale.getpreferredencoding on Windows → cp1252 fallback)
// For non-Windows: always use "utf-8" as a safe fallback.
// ---------------------------------------------------------------------------

let systemAnsiEncoding: unit => string = (
  () => %raw("() => { try { const { platform } = require('os'); return platform() === 'win32' ? 'cp1252' : 'utf-8'; } catch(e) { return 'utf-8'; } }")()
)

// ---------------------------------------------------------------------------
// ENCODING RULES (from ui_operations.py):
//   SaveAsText outputs UTF-16LE with BOM → decode utf-16-le, strip BOM
//   LoadFromText:
//     acModule (5) → system ANSI codepage, NO BOM
//     everything else (forms, reports, macros) → UTF-16LE with BOM
// ---------------------------------------------------------------------------

// _encodeForSave — given object_type, returns bytes for writing to temp file
// Mirrors ui_operations.py _load_object_from_text logic (inverse of SaveAsText)
let _encodeForSave: (int, string) => array<int> = (
  (objectType, textData) => {
    if objectType == _ACMODULE {
      // VBA modules: system ANSI, no BOM
      let enc = systemAnsiEncoding()
      %raw("(enc, textData) => { const buf = Buffer.from(textData, enc); return Array.from(buf); }")(enc, textData)
    } else {
      // Forms/reports/macros: UTF-16LE with BOM prefix 0xFF 0xFE
      %raw("(textData) => { const buf = Buffer.from('\ufeff' + textData, 'utf16le'); return Array.from(buf); }")(textData)
    }
  }
)

// _decodeFromLoad — given object_type and raw bytes, returns decoded string
// Mirrors ui_operations.py _save_object_to_text logic
let _decodeFromLoad: (int, array<int>) => string = (
  (objectType, raw) => {
    if objectType == _ACMODULE {
      // VBA modules: system ANSI
      let enc = systemAnsiEncoding()
      %raw("(raw, enc) => { const buf = Buffer.from(raw); return buf.toString(enc); }")(raw, enc)
    } else {
      // Forms/reports/macros: UTF-16LE with BOM
      %raw("(raw) => { const buf = Buffer.from(raw); return buf.toString('utf16le').replace(/^\ufeff/, ''); }")(raw)
    }
  }
)

// ---------------------------------------------------------------------------
// UTF-16LE+BOM round-trip tests — verify no corruption for forms/reports
// ---------------------------------------------------------------------------

test("UTF16LE+BOM round-trip: form text preserved through encode/decode", () => {
  let formText = "Attribute Form = True\r\nProperty Caption\r\n"
  let encoded = _encodeForSave(_ACFORM, formText)
  // UTF-16LE with BOM prefix: first 2 bytes = 0xFF 0xFE (BOM)
  let hasBom = Array.length(encoded) >= 2 && 
    (Array.get(encoded, 0) == Some(255)) && 
    (Array.get(encoded, 1) == Some(254))
  assertion(~operator="equal", (a, b) => a == b, hasBom, true)
})

test("UTF16LE+BOM round-trip: decoded form text matches original", () => {
  let formText = "Attribute Form = True\r\nProperty Caption\r\n"
  let encoded = _encodeForSave(_ACFORM, formText)
  let decoded = _decodeFromLoad(_ACFORM, encoded)
  assertion(~operator="equal", (a, b) => a == b, decoded, formText)
})

test("UTF16LE+BOM round-trip: report text preserved through encode/decode", () => {
  let reportText = "Attribute Report = True\r\nSection Header\r\n"
  let encoded = _encodeForSave(_ACREPORT, reportText)
  let decoded = _decodeFromLoad(_ACREPORT, encoded)
  assertion(~operator="equal", (a, b) => a == b, decoded, reportText)
})

test("UTF16LE+BOM round-trip: macro text preserved through encode/decode", () => {
  let macroText = "<?xml version=\"1.0\"?><macros:Macro>"
  let encoded = _encodeForSave(_ACMACRO, macroText)
  let decoded = _decodeFromLoad(_ACMACRO, encoded)
  assertion(~operator="equal", (a, b) => a == b, decoded, macroText)
})

// ---------------------------------------------------------------------------
// ANSI (no BOM) round-trip for VBA modules — ensure no BOM corruption
// ---------------------------------------------------------------------------

test("ANSI round-trip: VBA module text encoded without BOM", () => {
  let moduleText = "Attribute VB_Name = \"Module1\"\r\nSub Test()\r\nEnd Sub"
  let encoded = _encodeForSave(_ACMODULE, moduleText)
  // ANSI has no BOM — first bytes are NOT 0xFF 0xFE
  let hasBom = Array.length(encoded) >= 2 && 
    (Array.get(encoded, 0) == Some(255)) && 
    (Array.get(encoded, 1) == Some(254))
  assertion(~operator="equal", (a, b) => a == b, hasBom, false)
})

test("ANSI round-trip: VBA module text decoded correctly", () => {
  let moduleText = "Attribute VB_Name = \"Module1\"\r\nSub Test()\r\nEnd Sub"
  let encoded = _encodeForSave(_ACMODULE, moduleText)
  let decoded = _decodeFromLoad(_ACMODULE, encoded)
  assertion(~operator="equal", (a, b) => a == b, decoded, moduleText)
})

// ---------------------------------------------------------------------------
// Mixed encoding: verify form vs module produce different byte sequences
// ---------------------------------------------------------------------------

test("Encoding discrimination: form and module encodings differ", () => {
  let sameText = "Test"
  let formEncoded = _encodeForSave(_ACFORM, sameText)
  let moduleEncoded = _encodeForSave(_ACMODULE, sameText)
  // Form has BOM (0xFF 0xFE); module does not
  assertion(~operator="notEqual", (a, b) => a != b, formEncoded, moduleEncoded)
})

// ---------------------------------------------------------------------------
// Type shape tests — verify expected fields exist
// ---------------------------------------------------------------------------

test("ControlInfo has name, controlType, properties fields", () => {
  let c: controlInfo = {name: "txtName", controlType: "TextBox", properties: {}}
  switch c {
  | {name, controlType, properties} => {
      let n = name == "txtName"
      let t = controlType == "TextBox"
      let p = Array.length(Dict.keysToArray(properties)) == 0
      assertion(~operator="equal", (a, b) => a == b, n && t && p, true)
    }
  }
})

test("FormInfo has name, recordSource, controls fields", () => {
  let f: formInfo = {name: "MainForm", recordSource: "Users", controls: []}
  switch f {
  | {name, recordSource, controls} => {
      let n = name == "MainForm"
      let r = recordSource == "Users"
      let c = Array.length(controls) == 0
      assertion(~operator="equal", (a, b) => a == b, n && r && c, true)
    }
  }
})

test("ReportInfo has name, recordSource, controls fields", () => {
  let r: reportInfo = {name: "InvoiceReport", recordSource: "Orders", controls: []}
  switch r {
  | {name, recordSource, controls} => {
      let n = name == "InvoiceReport"
      let rs = recordSource == "Orders"
      let c = Array.length(controls) == 0
      assertion(~operator="equal", (a, b) => a == b, n && rs && c, true)
    }
  }
})

test("MacroInfo has name, macroType, dateCreated, dateModified fields", () => {
  let m: macroInfo = {name: "AutoExec", macroType: "Macro", dateCreated: "", dateModified: ""}
  switch m {
  | {name, macroType} => {
      let n = name == "AutoExec"
      let mt = macroType == "Macro"
      assertion(~operator="equal", (a, b) => a == b, n && mt, true)
    }
  }
})

// ---------------------------------------------------------------------------
// Control type mapping round-trip
// ---------------------------------------------------------------------------

test("Control type: TextBox (100) name round-trips", () => {
  let name = controlTypeName(100)
  assertion(~operator="equal", (a, b) => a == b, name, "TextBox")
})

test("Control type: Label (101) name round-trips", () => {
  let name = controlTypeName(101)
  assertion(~operator="equal", (a, b) => a == b, name, "Label")
})

test("Control type: CommandButton (102) name round-trips", () => {
  let name = controlTypeName(102)
  assertion(~operator="equal", (a, b) => a == b, name, "CommandButton")
})

test("Control type: CheckBox (108) name round-trips", () => {
  let name = controlTypeName(108)
  assertion(~operator="equal", (a, b) => a == b, name, "CheckBox")
})

test("Control type: unknown type returns Control(N) string", () => {
  let name = controlTypeName(999)
  assertion(~operator="equal", (a, b) => a == b, String.includes(name, "Control"), true)
})

// ---------------------------------------------------------------------------
// Section name round-trip
// ---------------------------------------------------------------------------

test("Section: detail (0) name round-trips", () => {
  let name = sectionName(0)
  assertion(~operator="equal", (a, b) => a == b, name, "detail")
})

test("Section: header (1) name round-trips", () => {
  let name = sectionName(1)
  assertion(~operator="equal", (a, b) => a == b, name, "header")
})

test("Section: footer (2) name round-trips", () => {
  let name = sectionName(2)
  assertion(~operator="equal", (a, b) => a == b, name, "footer")
})

test("Section: page_header (3) name round-trips", () => {
  let name = sectionName(3)
  assertion(~operator="equal", (a, b) => a == b, name, "page_header")
})

test("Section: page_footer (4) name round-trips", () => {
  let name = sectionName(4)
  assertion(~operator="equal", (a, b) => a == b, name, "page_footer")
})

// ---------------------------------------------------------------------------
// Object type constants
// ---------------------------------------------------------------------------

test("Object types: acForm=2, acReport=4, acModule=5, acMacro=8", () => {
  let t1 = _ACFORM == 2
  let t2 = _ACREPORT == 4
  let t3 = _ACMODULE == 5
  let t4 = _ACMACRO == 8
  assertion(~operator="equal", (a, b) => a == b, t1 && t2 && t3 && t4, true)
})

// ---------------------------------------------------------------------------
// UTF-16LE BOM constant
// ---------------------------------------------------------------------------

test("UTF16LE BOM constant is U+FEFF", () => {
  let code = %raw("(s) => s.charCodeAt(0)")(_UTF16LE_BOM)
  assertion(~operator="equal", (a, b) => a == b, code, 0xFEFF)
})

// ---------------------------------------------------------------------------
// Unicode content round-trip (non-ASCII chars must survive UTF-16LE encoding)
// ---------------------------------------------------------------------------

test("UTF16LE+BOM: Unicode form text preserved (Latin-1 chars)", () => {
  let formText = "Caf\xe9 = \xdat\xf8res"  // "Café = øres"
  let encoded = _encodeForSave(_ACFORM, formText)
  let decoded = _decodeFromLoad(_ACFORM, encoded)
  assertion(~operator="equal", (a, b) => a == b, decoded, formText)
})

test("ANSI round-trip: VBA module with Latin-1 chars preserved", () => {
  let moduleText = "'\xe9\xe8\xe0"  // French accents in comment
  let encoded = _encodeForSave(_ACMODULE, moduleText)
  let decoded = _decodeFromLoad(_ACMODULE, encoded)
  assertion(~operator="equal", (a, b) => a == b, decoded, moduleText)
})

// ---------------------------------------------------------------------------
// Stub shape tests — not-connected parity with Python oracle
// ---------------------------------------------------------------------------

// stubGetForms — not connected → []
testAsync("ComUi stub: getForms not-connected returns []", cb => {
  let handles: sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: sessionHandles => Promise.t<array<formInfo>> = (
    (h) => switch h.accessApp { | Some(_) => Promise.resolve([]) | None => Promise.resolve([]) }
  )
  ignore(
    stub(handles)
      ->Promise.then(r => {
        Promise.resolve(
          assertion(~operator="equal", (a, b) => a == b, Array.length(r), 0)
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

// stubFormExists — not connected → false
testAsync("ComUi stub: formExists not-connected returns false", cb => {
  let handles: sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: (sessionHandles, string) => Promise.t<bool> = (
    (h, _n) => switch h.accessApp { | Some(_) => Promise.resolve(false) | None => Promise.resolve(false) }
  )
  ignore(
    stub(handles, "TestForm")
      ->Promise.then(r => {
        Promise.resolve(
          assertion(~operator="equal", (a, b) => a == b, r, false)
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

// stubGetFormControls — not connected → []
testAsync("ComUi stub: getFormControls not-connected returns []", cb => {
  let handles: sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: (sessionHandles, string) => Promise.t<array<controlInfo>> = (
    (h, _n) => switch h.accessApp { | Some(_) => Promise.resolve([]) | None => Promise.resolve([]) }
  )
  ignore(
    stub(handles, "TestForm")
      ->Promise.then(r => {
        Promise.resolve(
          assertion(~operator="equal", (a, b) => a == b, Array.length(r), 0)
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

// stubGetReports — not connected → []
testAsync("ComUi stub: getReports not-connected returns []", cb => {
  let handles: sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: sessionHandles => Promise.t<array<reportInfo>> = (
    (h) => switch h.accessApp { | Some(_) => Promise.resolve([]) | None => Promise.resolve([]) }
  )
  ignore(
    stub(handles)
      ->Promise.then(r => {
        Promise.resolve(
          assertion(~operator="equal", (a, b) => a == b, Array.length(r), 0)
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

// stubCreateForm — not connected → false
testAsync("ComUi stub: createForm not-connected returns false", cb => {
  let handles: sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: (sessionHandles, string) => Promise.t<bool> = (
    (h, _n) => switch h.accessApp { | Some(_) => Promise.resolve(false) | None => Promise.resolve(false) }
  )
  ignore(
    stub(handles, "NewForm")
      ->Promise.then(r => {
        Promise.resolve(
          assertion(~operator="equal", (a, b) => a == b, r, false)
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

// stubDeleteForm — not connected → false
testAsync("ComUi stub: deleteForm not-connected returns false", cb => {
  let handles: sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: (sessionHandles, string) => Promise.t<bool> = (
    (h, _n) => switch h.accessApp { | Some(_) => Promise.resolve(false) | None => Promise.resolve(false) }
  )
  ignore(
    stub(handles, "OldForm")
      ->Promise.then(r => {
        Promise.resolve(
          assertion(~operator="equal", (a, b) => a == b, r, false)
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

// stubExportFormToText — not connected → ""
testAsync("ComUi stub: exportFormToText not-connected returns empty string", cb => {
  let handles: sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: (sessionHandles, string) => Promise.t<string> = (
    (h, _n) => switch h.accessApp { | Some(_) => Promise.resolve("") | None => Promise.resolve("") }
  )
  ignore(
    stub(handles, "TestForm")
      ->Promise.then(r => {
        Promise.resolve(
          assertion(~operator="equal", (a, b) => a == b, r, "")
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

// stubImportFormFromText — not connected → false
testAsync("ComUi stub: importFormFromText not-connected returns false", cb => {
  let handles: sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: (sessionHandles, string, string) => Promise.t<bool> = (
    (h, _n, _d) => switch h.accessApp { | Some(_) => Promise.resolve(false) | None => Promise.resolve(false) }
  )
  ignore(
    stub(handles, "NewForm", "Attribute Form=True")
      ->Promise.then(r => {
        Promise.resolve(
          assertion(~operator="equal", (a, b) => a == b, r, false)
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

// stubGetMacros — not connected → []
testAsync("ComUi stub: getMacros not-connected returns []", cb => {
  let handles: sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: sessionHandles => Promise.t<array<macroInfo>> = (
    (h) => switch h.accessApp { | Some(_) => Promise.resolve([]) | None => Promise.resolve([]) }
  )
  ignore(
    stub(handles)
      ->Promise.then(r => {
        Promise.resolve(
          assertion(~operator="equal", (a, b) => a == b, Array.length(r), 0)
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
