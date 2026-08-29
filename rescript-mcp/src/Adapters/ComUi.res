// ComUi.res — UI forms/reports/controls/macros + SaveAsText/LoadFromText encoding
// Task 4.2 GREEN: UI + SaveAsText/LoadFromText ops
// Mirrors src/ms_access_mcp/adapters/ui_operations.py
// Encoding rules:
//   SaveAsText: outputs UTF-16LE with BOM → decode utf-16-le, strip BOM
//   LoadFromText: acModule=5 → system ANSI (no BOM); others → UTF-16LE with BOM

// ---------------------------------------------------------------------------
// Object type constants (Access Ac... enum values)
// ---------------------------------------------------------------------------

let acForm: int = 2
let acReport: int = 4
let acModule: int = 5
let acMacro: int = 8

// ---------------------------------------------------------------------------
// Section id constants
// ---------------------------------------------------------------------------

let sectionDetail: int = 0
let sectionHeader: int = 1
let sectionFooter: int = 2
let sectionPageHeader: int = 3
let sectionPageFooter: int = 4

// VBE component types
let _vbStandardModule: int = 1
let _vbClassModule: int = 2

// ---------------------------------------------------------------------------
// Control type name → Access AcControlType id
// ---------------------------------------------------------------------------

let controlTypeId: string => int = (
  (name) => switch name {
    | "TextBox" => 100
    | "Label" => 101
    | "CommandButton" => 102
    | "OptionButton" => 103
    | "ComboBox" => 104
    | "ListBox" => 105
    | "SubForm" => 106
    | "ToggleButton" => 107
    | "CheckBox" => 108
    | "OptionGroup" => 109
    | "TabControl" => 110
    | "Page" => 111
    | "Image" => 112
    | "BoundObjectFrame" => 114
    | "ObjectFrame" => 115
    | "Line" => 118
    | "Rectangle" => 119
    | "PageBreak" => 120
    | "Attachment" => 122
    | "NavigationButton" => 123
    | "NavigationControl" => 124
    | "WebBrowserControl" => 126
    | "EmptyCell" => 128
    | _ => 0
  }
)

// ---------------------------------------------------------------------------
// Control type id → readable name
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
// Section id → name
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
// Named result types for collection items
// ---------------------------------------------------------------------------

type formSummary = {
  name: string,
  recordSource: string,
}

type reportSummary = {
  name: string,
  recordSource: string,
}

type controlSummary = {
  name: string,
  controlType: string,
  properties: dict<string>,
}

type sectionSummary = {
  index: int,
  name: string,
  sectionType: string,
  visible: bool,
  height: int,
}

type macroSummary = {
  name: string,
  macroType: string,
}

// ---------------------------------------------------------------------------
// COM object bridges
// ---------------------------------------------------------------------------

// Identity cast: winax returns JSON.t at runtime but we need ComInterfaces.comObject
// The actual COM object is passed through unchanged — only the type annotation differs
let toComObject: JSON.t => ComInterfaces.comObject = (j) => %raw("(j) => j")(j)

// ---------------------------------------------------------------------------
// Session state helpers
// ---------------------------------------------------------------------------

let _connected: ComInterfaces.sessionHandles => bool = (
  (h) => switch h.accessApp { | Some(_) => true | None => false }
)

@val external _nullComObject: ComInterfaces.comObject = "null"

let _app: ComInterfaces.sessionHandles => ComInterfaces.comObject = (
  (h) => switch h.accessApp { | Some(a) => a | None => _nullComObject }
)

// ---------------------------------------------------------------------------
// Encoding helpers (exposed for testing)
// ---------------------------------------------------------------------------

// _systemAnsiEncoding — returns the system ANSI encoding name.
// On Windows, Access uses the system ANSI codepage (cp1252); elsewhere utf-8.
let _systemAnsiEncoding: unit => string = (
  () => {
    if NodeJs.Os.platform() == "win32" {
      "cp1252"
    } else {
      "utf-8"
    }
  }
)

// _encodeForSave — encode text for SaveAsText.
// SaveAsText always outputs UTF-16LE with BOM (2-byte header).
// Returns bytes including the UTF-16LE BOM prefix (0xFF 0xFE).
let _encodeForSave: (int, string) => array<int> = (
  (objectType, text) => {
    if objectType == 5 {
      // acModule: ANSI encoding, no BOM — use TsBridge codec helper
      Bindings.TsBridge.encodeCp1252(text)
    } else {
      // others: UTF-16LE with BOM
      let bom = NodeJs.Buffer.fromStringWithEncoding("\ufeff", NodeJs.StringEncoding.utf16le)
      let textBuf = NodeJs.Buffer.fromStringWithEncoding(text, NodeJs.StringEncoding.utf16le)
      let combined = NodeJs.Buffer.concat([bom, textBuf])
      Bindings.TsBridge.bufferToBytes(combined)
    }
  }
)

// _decodeFromLoad — decode bytes from LoadFromText.
// acModule=5 → system ANSI (no BOM); others → UTF-16LE with BOM.
let _decodeFromLoad: (int, array<int>) => string = (
  (objectType, bytes) => {
    if objectType == 5 {
      // acModule: ANSI decoding, no BOM
      Bindings.TsBridge.decodeCp1252(bytes)
    } else {
      // others: UTF-16LE with BOM (strip first 2 bytes)
      Bindings.TsBridge.decodeUtf16LeSkipBom(bytes)
    }
  }
)

// ---------------------------------------------------------------------------
// SaveAsText / LoadFromText helpers
// ---------------------------------------------------------------------------

// _saveObjectToText — export Access object via SaveAsText
// objectType: acForm=2, acReport=4, acModule=5, acMacro=8
// Returns text content (UTF-16LE decoded, BOM stripped) or "" on failure.
let _saveObjectToText: (ComInterfaces.sessionHandles, int, string) => Promise.t<string> = (
  (handles, objectType, objectName) => {
    if !_connected(handles) { Promise.resolve("") }
    else {
      let app = _app(handles)
      Bindings.JsCom._saveObjectToText(app, objectType, objectName)
        ->Promise.then(result => Promise.resolve(result))
        ->Promise.catch(_ => Promise.resolve(""))
    }
  }
)

// _loadObjectFromText — import Access object via LoadFromText
// objectType: acForm=2, acReport=4, acModule=5, acMacro=8
// Encoding rules:
//   acModule → system ANSI codepage, NO BOM
//   others → UTF-16LE with BOM
// Returns true on success, false on failure.
let _loadObjectFromText: (ComInterfaces.sessionHandles, int, string, string) => Promise.t<bool> = (
  (handles, objectType, objectName, textData) => {
    if !_connected(handles) { Promise.resolve(false) }
    else {
      let app = _app(handles)
      Bindings.JsCom._loadObjectFromText(app, objectType, objectName, textData)
        ->Promise.then(r => Promise.resolve(r))
        ->Promise.catch(_ => Promise.resolve(false))
    }
  }
)

// ---------------------------------------------------------------------------
// _getAllCollection — get AllForms / AllReports / AllMacros
// ---------------------------------------------------------------------------

let _getAllCollection: (ComInterfaces.sessionHandles, string) => Promise.t<option<JSON.t>> = (
  (handles, collectionName) => {
    if !_connected(handles) { Promise.resolve(None) }
    else {
      let app = _app(handles)
      Bindings.Winax.WINAX_BINDING.get(app, "CurrentProject")
        ->Promise.then(r => {
          switch r { | Error(_) => Promise.resolve(None) | Ok(cp) => {
            Bindings.Winax.WINAX_BINDING.get(toComObject(cp), collectionName)
              ->Promise.then(r2 => switch r2 { | Error(_) => Promise.resolve(None) | Ok(v) => Promise.resolve(Some(v)) })
              ->Promise.catch(_ => Promise.resolve(None))
          }}
        })
        ->Promise.catch(_ => Promise.resolve(None))
    }
  }
)

// ---------------------------------------------------------------------------
// _collectionItemNames — gather names from a collection (AllForms/AllReports/AllMacros)
// ---------------------------------------------------------------------------

let _collectionItemNames: (ComInterfaces.sessionHandles, string) => Promise.t<array<formSummary>> = (
  (handles, collectionName) => {
    _getAllCollection(handles, collectionName)
      ->Promise.then(opt => {
        switch opt {
          | None => Promise.resolve([])
          | Some(col) => {
            let co = toComObject(col)
            Bindings.Winax.WINAX_BINDING.get(co, "Count")
              ->Promise.then(r => {
                let count = switch r { | Ok(JSON.Number(x)) => Float.toInt(x) | _ => 0 }
                if count == 0 { Promise.resolve([]) }
                else {
                  let rec gather: (int, int, array<formSummary>) => Promise.t<array<formSummary>> = (
                    (i, total, acc) => {
                      if i >= total { Promise.resolve(acc) }
                      else {
                        Bindings.Winax.WINAX_BINDING.invoke(co, "Item", [ComInterfaces.VInt(i)])
                          ->Promise.then(itemResult => {
                            switch itemResult {
                              | Error(_) => gather(i + 1, total, acc)
                              | Ok(item) => {
                                Bindings.Winax.WINAX_BINDING.get(toComObject(item), "Name")
                                  ->Promise.then(nmResult => {
                                    let nm = switch nmResult { | Ok(JSON.String(s)) => s | _ => "" }
                                    let entry: formSummary = {name: nm, recordSource: ""}
                                    gather(i + 1, total, Array.concat(acc, [entry]))
                                  })
                                  ->Promise.catch(_ => gather(i + 1, total, acc))
                              }
                            }
                          })
                          ->Promise.catch(_ => gather(i + 1, total, acc))
                      }
                    }
                  )
                  gather(0, count, [])
                }
              })
              ->Promise.catch(_ => Promise.resolve([]))
          }
        }
      })
      ->Promise.catch(_ => Promise.resolve([]))
  }
)

// ---------------------------------------------------------------------------
// _collectionExists — check if item exists in collection by name
// ---------------------------------------------------------------------------

let _collectionExists: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool> = (
  (handles, collectionName, itemName) => {
    _getAllCollection(handles, collectionName)
      ->Promise.then(opt => {
        switch opt { | None => Promise.resolve(false) | Some(col) => {
          let co = toComObject(col)
          Bindings.Winax.WINAX_BINDING.get(co, "Count")
            ->Promise.then(r => {
              let count = switch r { | Ok(JSON.Number(x)) => Float.toInt(x) | _ => 0 }
              if count == 0 { Promise.resolve(false) }
              else {
                let rec find: (int) => Promise.t<bool> = (
                  (i) => {
                    if i >= count { Promise.resolve(false) }
                    else {
                      Bindings.Winax.WINAX_BINDING.invoke(co, "Item", [ComInterfaces.VInt(i)])
                        ->Promise.then(itemResult => {
                          switch itemResult { | Error(_) => find(i + 1) | Ok(item) => {
                            Bindings.Winax.WINAX_BINDING.get(toComObject(item), "Name")
                              ->Promise.then(nm => {
                                switch nm { | Ok(JSON.String(s)) if s == itemName => Promise.resolve(true) | _ => find(i + 1) }
                              })
                              ->Promise.catch(_ => find(i + 1))
                          }}
                        })
                        ->Promise.catch(_ => find(i + 1))
                    }
                  }
                )
                find(0)
              }
            })
            ->Promise.catch(_ => Promise.resolve(false))
        }}
      })
      ->Promise.catch(_ => Promise.resolve(false))
  }
)

// ---------------------------------------------------------------------------
// FORM OPERATIONS
// ---------------------------------------------------------------------------

// getForms — enumerate all forms via CurrentProject.AllForms
let getForms: ComInterfaces.sessionHandles => Promise.t<array<formSummary>> = (
  (handles) => {
    if !_connected(handles) { Promise.resolve([]) }
    else { _collectionItemNames(handles, "AllForms") }
  }
)

// formExists — check if form exists in AllForms
let formExists: (ComInterfaces.sessionHandles, string) => Promise.t<bool> = (
  (handles, formName) => {
    if !_connected(handles) { Promise.resolve(false) }
    else { _collectionExists(handles, "AllForms", formName) }
  }
)

// getFormControls — get all controls in a form (opens in design view)
let getFormControls: (ComInterfaces.sessionHandles, string) => Promise.t<array<controlSummary>> = (
  (handles, formName) => {
    if !_connected(handles) { Promise.resolve([]) }
    else {
      let app = _app(handles)
      Bindings.JsCom.getFormControls(app, formName)
        ->Promise.then(items => Promise.resolve(items :> array<controlSummary>))
        ->Promise.catch(_ => Promise.resolve([]))
    }
  }
)

// getFormProperties — get all form properties (opens in design view)
let getFormProperties: (ComInterfaces.sessionHandles, string) => Promise.t<dict<string>> = (
  (handles, formName) => {
    if !_connected(handles) { Promise.resolve(Dict.make()) }
    else {
      let app = _app(handles)
      Bindings.JsCom.getFormProperties(app, formName)
        ->Promise.then(d => Promise.resolve(d))
        ->Promise.catch(_ => Promise.resolve(Dict.make()))
    }
  }
)

// setFormProperty — set a single form property (opens in design view)
let setFormProperty: (ComInterfaces.sessionHandles, string, string, string) => Promise.t<bool> = (
  (handles, formName, propertyName, value) => {
    if !_connected(handles) { Promise.resolve(false) }
    else {
      let app = _app(handles)
      Bindings.JsCom.setFormProperty(app, formName, propertyName, value)
        ->Promise.then(r => Promise.resolve(r))
        ->Promise.catch(_ => Promise.resolve(false))
    }
  }
)

// createForm — create a new blank form via DoCmd.CreateForm
let createForm: (ComInterfaces.sessionHandles, string) => Promise.t<bool> = (
  (handles, formName) => {
    if !_connected(handles) { Promise.resolve(false) }
    else {
      let app = _app(handles)
      Bindings.JsCom.createForm(app, formName)
        ->Promise.then(r => Promise.resolve(r))
        ->Promise.catch(_ => Promise.resolve(false))
    }
  }
)

// deleteForm — delete a form via DoCmd.DeleteObject(acForm=2, name)
let deleteForm: (ComInterfaces.sessionHandles, string) => Promise.t<bool> = (
  (handles, formName) => {
    if !_connected(handles) { Promise.resolve(false) }
    else {
      let app = _app(handles)
      Bindings.Winax.WINAX_BINDING.get(app, "DoCmd")
        ->Promise.then(r => {
          switch r { | Error(_) => Promise.resolve(false) | Ok(docmd) => {
            Bindings.Winax.WINAX_BINDING.invoke(toComObject(docmd), "DeleteObject", [ComInterfaces.VInt(acForm), ComInterfaces.VStr(formName)])
              ->Promise.then(_ => Promise.resolve(true))
              ->Promise.catch(_ => Promise.resolve(false))
          }}
        })
        ->Promise.catch(_ => Promise.resolve(false))
    }
  }
)

// renameForm — rename a form via DoCmd.Rename(newName, acForm, oldName)
let renameForm: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool> = (
  (handles, oldName, newName) => {
    if !_connected(handles) { Promise.resolve(false) }
    else {
      let app = _app(handles)
      Bindings.Winax.WINAX_BINDING.get(app, "DoCmd")
        ->Promise.then(r => {
          switch r { | Error(_) => Promise.resolve(false) | Ok(docmd) => {
            Bindings.Winax.WINAX_BINDING.invoke(toComObject(docmd), "Rename", [ComInterfaces.VStr(newName), ComInterfaces.VInt(acForm), ComInterfaces.VStr(oldName)])
              ->Promise.then(_ => Promise.resolve(true))
              ->Promise.catch(_ => Promise.resolve(false))
          }}
        })
        ->Promise.catch(_ => Promise.resolve(false))
    }
  }
)

// exportFormToText — export form definition via SaveAsText(acForm=2)
let exportFormToText: (ComInterfaces.sessionHandles, string) => Promise.t<string> = (
  (handles, formName) => _saveObjectToText(handles, acForm, formName)
)

// importFormFromText — import form definition via LoadFromText(acForm=2)
let importFormFromText: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool> = (
  (handles, formName, textData) => _loadObjectFromText(handles, acForm, formName, textData)
)

// ---------------------------------------------------------------------------
// REPORT OPERATIONS
// ---------------------------------------------------------------------------

// getReports — enumerate all reports via CurrentProject.AllReports
let getReports: ComInterfaces.sessionHandles => Promise.t<array<reportSummary>> = (
  (handles) => {
    if !_connected(handles) { Promise.resolve([]) }
    else {
      _getAllCollection(handles, "AllReports")
        ->Promise.then(opt => {
          switch opt {
            | None => Promise.resolve([])
            | Some(col) => {
              let ro = toComObject(col)
              Bindings.Winax.WINAX_BINDING.get(ro, "Count")
                ->Promise.then(r => {
                  let count = switch r { | Ok(JSON.Number(x)) => Float.toInt(x) | _ => 0 }
                  if count == 0 { Promise.resolve([]) }
                  else {
                    let rec gather: (int, int, array<reportSummary>) => Promise.t<array<reportSummary>> = (
                      (i, total, acc) => {
                        if i >= total { Promise.resolve(acc) }
                        else {
                          Bindings.Winax.WINAX_BINDING.invoke(ro, "Item", [ComInterfaces.VInt(i)])
                            ->Promise.then(itemResult => {
                              switch itemResult {
                                | Error(_) => gather(i + 1, total, acc)
                                | Ok(item) => {
                                  Bindings.Winax.WINAX_BINDING.get(toComObject(item), "Name")
                                    ->Promise.then(nmResult => {
                                      let nm = switch nmResult { | Ok(JSON.String(s)) => s | _ => "" }
                                      let entry: reportSummary = {name: nm, recordSource: ""}
                                      gather(i + 1, total, Array.concat(acc, [entry]))
                                    })
                                    ->Promise.catch(_ => gather(i + 1, total, acc))
                                }
                              }
                            })
                            ->Promise.catch(_ => gather(i + 1, total, acc))
                        }
                      }
                    )
                    gather(0, count, [])
                  }
                })
                ->Promise.catch(_ => Promise.resolve([]))
            }
          }
        })
        ->Promise.catch(_ => Promise.resolve([]))
    }
  }
)

// reportExists — check if report exists in AllReports
let reportExists: (ComInterfaces.sessionHandles, string) => Promise.t<bool> = (
  (handles, reportName) => {
    if !_connected(handles) { Promise.resolve(false) }
    else { _collectionExists(handles, "AllReports", reportName) }
  }
)

// getReportControls — get all controls in a report (opens in design view)
let getReportControls: (ComInterfaces.sessionHandles, string) => Promise.t<array<controlSummary>> = (
  (handles, reportName) => {
    if !_connected(handles) { Promise.resolve([]) }
    else {
      let app = _app(handles)
      Bindings.JsCom.getReportControls(app, reportName)
        ->Promise.then(items => Promise.resolve(items :> array<controlSummary>))
        ->Promise.catch(_ => Promise.resolve([]))
    }
  }
)

// createReport — create a new blank report via DoCmd.CreateReport
let createReport: (ComInterfaces.sessionHandles, string) => Promise.t<bool> = (
  (handles, reportName) => {
    if !_connected(handles) { Promise.resolve(false) }
    else {
      let app = _app(handles)
      Bindings.JsCom.createReport(app, reportName)
        ->Promise.then(r => Promise.resolve(r))
        ->Promise.catch(_ => Promise.resolve(false))
    }
  }
)

// deleteReport — delete a report via DoCmd.DeleteObject(acReport=4, name)
let deleteReport: (ComInterfaces.sessionHandles, string) => Promise.t<bool> = (
  (handles, reportName) => {
    if !_connected(handles) { Promise.resolve(false) }
    else {
      let app = _app(handles)
      Bindings.Winax.WINAX_BINDING.get(app, "DoCmd")
        ->Promise.then(r => {
          switch r { | Error(_) => Promise.resolve(false) | Ok(docmd) => {
            Bindings.Winax.WINAX_BINDING.invoke(toComObject(docmd), "DeleteObject", [ComInterfaces.VInt(acReport), ComInterfaces.VStr(reportName)])
              ->Promise.then(_ => Promise.resolve(true))
              ->Promise.catch(_ => Promise.resolve(false))
          }}
        })
        ->Promise.catch(_ => Promise.resolve(false))
    }
  }
)

// exportReportToText — export report definition via SaveAsText(acReport=4)
let exportReportToText: (ComInterfaces.sessionHandles, string) => Promise.t<string> = (
  (handles, reportName) => _saveObjectToText(handles, acReport, reportName)
)

// importReportFromText — import report definition via LoadFromText(acReport=4)
let importReportFromText: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool> = (
  (handles, reportName, textData) => _loadObjectFromText(handles, acReport, reportName, textData)
)

// ---------------------------------------------------------------------------
// MACRO OPERATIONS
// ---------------------------------------------------------------------------

// getMacros — enumerate all macros via CurrentProject.AllMacros
let getMacros: ComInterfaces.sessionHandles => Promise.t<array<macroSummary>> = (
  (handles) => {
    if !_connected(handles) { Promise.resolve([]) }
    else {
      _getAllCollection(handles, "AllMacros")
        ->Promise.then(opt => {
          switch opt {
            | None => Promise.resolve([])
            | Some(col) => {
              let mo = toComObject(col)
              Bindings.Winax.WINAX_BINDING.get(mo, "Count")
                ->Promise.then(r => {
                  let count = switch r { | Ok(JSON.Number(x)) => Float.toInt(x) | _ => 0 }
                  if count == 0 { Promise.resolve([]) }
                  else {
                    let rec gather: (int, int, array<macroSummary>) => Promise.t<array<macroSummary>> = (
                      (i, total, acc) => {
                        if i >= total { Promise.resolve(acc) }
                        else {
                          Bindings.Winax.WINAX_BINDING.invoke(mo, "Item", [ComInterfaces.VInt(i)])
                            ->Promise.then(itemResult => {
                              switch itemResult {
                                | Error(_) => gather(i + 1, total, acc)
                                | Ok(item) => {
                                  Bindings.Winax.WINAX_BINDING.get(toComObject(item), "Name")
                                    ->Promise.then(nmResult => {
                                      let nm = switch nmResult { | Ok(JSON.String(s)) => s | _ => "" }
                                      let entry: macroSummary = {name: nm, macroType: "Macro"}
                                      gather(i + 1, total, Array.concat(acc, [entry]))
                                    })
                                    ->Promise.catch(_ => gather(i + 1, total, acc))
                                }
                              }
                            })
                            ->Promise.catch(_ => gather(i + 1, total, acc))
                        }
                      }
                    )
                    gather(0, count, [])
                  }
                })
                ->Promise.catch(_ => Promise.resolve([]))
            }
          }
        })
        ->Promise.catch(_ => Promise.resolve([]))
    }
  }
)

// exportMacroToText — export macro definition via SaveAsText(acMacro=8)
let exportMacroToText: (ComInterfaces.sessionHandles, string) => Promise.t<string> = (
  (handles, macroName) => _saveObjectToText(handles, acMacro, macroName)
)

// importMacroFromText — import macro definition via LoadFromText(acMacro=8)
let importMacroFromText: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool> = (
  (handles, macroName, textData) => _loadObjectFromText(handles, acMacro, macroName, textData)
)

// ---------------------------------------------------------------------------
// CONTROL OPERATIONS
// ---------------------------------------------------------------------------

// getControlProperties — get all properties of a control in a form
let getControlProperties: (ComInterfaces.sessionHandles, string, string) => Promise.t<dict<string>> = (
  (handles, formName, controlName) => {
    if !_connected(handles) { Promise.resolve(Dict.make()) }
    else {
      let app = _app(handles)
      Bindings.JsCom.getControlProperties(app, formName, controlName)
        ->Promise.then(d => Promise.resolve(d))
        ->Promise.catch(_ => Promise.resolve(Dict.make()))
    }
  }
)

// setControlProperty — set a property of a control in a form
let setControlProperty: (ComInterfaces.sessionHandles, string, string, string, string) => Promise.t<bool> = (
  (handles, formName, controlName, propertyName, value) => {
    if !_connected(handles) { Promise.resolve(false) }
    else {
      let app = _app(handles)
      Bindings.JsCom.setControlProperty(app, formName, controlName, propertyName, value)
        ->Promise.then(r => Promise.resolve(r))
        ->Promise.catch(_ => Promise.resolve(false))
    }
  }
)

// addControl — add a control to a form
let addControl: (ComInterfaces.sessionHandles, string, string, string, int) => Promise.t<bool> = (
  (handles, formName, controlType, controlName, section) => {
    if !_connected(handles) { Promise.resolve(false) }
    else {
      let typeInt = controlTypeId(controlType)
      if typeInt == 0 { Promise.resolve(false) }
      else {
        let app = _app(handles)
        Bindings.JsCom.addControl(app, formName, Int.toString(typeInt), controlName, section)
          ->Promise.then(r => Promise.resolve(r))
          ->Promise.catch(_ => Promise.resolve(false))
      }
    }
  }
)

// removeControl — remove a control from a form
let removeControl: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool> = (
  (handles, formName, controlName) => {
    if !_connected(handles) { Promise.resolve(false) }
    else {
      let app = _app(handles)
      Bindings.JsCom.removeControl(app, formName, controlName)
        ->Promise.then(r => Promise.resolve(r))
        ->Promise.catch(_ => Promise.resolve(false))
    }
  }
)

// ---------------------------------------------------------------------------
// FORM SECTION OPERATIONS
// ---------------------------------------------------------------------------

// getFormSections — get all sections of a form
let getFormSections: (ComInterfaces.sessionHandles, string) => Promise.t<array<sectionSummary>> = (
  (handles, formName) => {
    if !_connected(handles) { Promise.resolve([]) }
    else {
      let app = _app(handles)
      Bindings.JsCom.getFormSections(app, formName)
        ->Promise.then(items => Promise.resolve(items :> array<sectionSummary>))
        ->Promise.catch(_ => Promise.resolve([]))
    }
  }
)

// getFormSectionProperties — get all properties of a form section
let getFormSectionProperties: (ComInterfaces.sessionHandles, string, int) => Promise.t<dict<string>> = (
  (handles, formName, sectionId) => {
    if !_connected(handles) { Promise.resolve(Dict.make()) }
    else {
      let app = _app(handles)
      Bindings.JsCom.getFormSectionProperties(app, formName, sectionId)
        ->Promise.then(d => Promise.resolve(d))
        ->Promise.catch(_ => Promise.resolve(Dict.make()))
    }
  }
)

// setFormSectionProperty — set a single property of a form section
let setFormSectionProperty: (ComInterfaces.sessionHandles, string, int, string, string) => Promise.t<bool> = (
  (handles, formName, sectionId, propertyName, value) => {
    if !_connected(handles) { Promise.resolve(false) }
    else {
      let app = _app(handles)
      Bindings.JsCom.setFormSectionProperty(app, formName, sectionId, propertyName, value)
        ->Promise.then(r => Promise.resolve(r))
        ->Promise.catch(_ => Promise.resolve(false))
    }
  }
)
