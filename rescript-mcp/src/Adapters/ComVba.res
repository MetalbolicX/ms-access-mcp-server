// ComVba.res — VBA module CRUD + Application.Run via WINAX_BINDING
// Implements VBA operations against WINAX_BINDING + TrustedLocations
// Mirrors src/ms_access_mcp/adapters/vba_operations.py

// ---------------------------------------------------------------------------
// Types (mirrored from ComVba.resi)
// ---------------------------------------------------------------------------

type vbProcedureInfo = {
  name: string,
  procType: string,
  startLine: int,
  lineCount: int,
}

type compileResult = {
  success: bool,
  error: option<string>,
}

type moduleInfo = {
  name: string,
  moduleType: string,
  code: string,
}

type saveResult = {
  success: bool,
  savedModules: int,
  errors: array<string>,
}

// ---------------------------------------------------------------------------
// Compile command IDs (Access version varies)
// ---------------------------------------------------------------------------

let _COMPILE_CMD_IDS: array<int> = [301, 206, 317, 232]
let _VBE_STD_MODULE: int = 1
let _ACMODULE: int = 5

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

let _connected: ComInterfaces.sessionHandles => bool = (
  (h) => switch h.accessApp { | Some(_) => true | None => false }
)

@val external _nullComObject: ComInterfaces.comObject = "null"

let _app: ComInterfaces.sessionHandles => ComInterfaces.comObject = (
  (h) => switch h.accessApp { | Some(a) => a | None => _nullComObject }
)

// Identity cast JSON.t → comObject at the COM/JS boundary.
// comObject is typed as `unit` (opaque winax handle); JSON.t carries the
// actual runtime value. No typed FFI alternative exists without redesigning
// the public ComInterfaces.comObject type (tracked separately).
let _toComObject: JSON.t => ComInterfaces.comObject = (j) => %raw("(j) => j")(j)

// _exnMsg — safe error-message extraction from ReScript exn (JS Error wrapper).
// %raw only once; every catch site uses this helper instead of inlining.
let _exnMsg: exn => string = (e) => {
  let raw: option<string> = Bindings.TsBridge.exnMessage(e)
  switch raw { | Some(m) => m | None => "Unknown error" }
}

// ---------------------------------------------------------------------------
// _getVbProject — get first VBA project via VBE.VBProjects enumeration
// ---------------------------------------------------------------------------

let _getVbProject: ComInterfaces.sessionHandles => Promise.t<option<ComInterfaces.comObject>> = (
  (handles) => {
    if !_connected(handles) { Promise.resolve(None) }
    else {
      let app = _app(handles)
      Bindings.Winax.WINAX_BINDING.get(app, "VBE")
        ->Promise.then(result => {
          switch result { | Error(_) => Promise.resolve(None) | Ok(vbe) => Promise.resolve(Some(vbe)) }
        })
        ->Promise.then(optVbe => {
          switch optVbe {
          | None => Promise.resolve(None)
          | Some(vbe) => Bindings.Winax.WINAX_BINDING.get(_toComObject(vbe), "VBProjects")
              ->Promise.then(r => Promise.resolve(switch r { | Error(_) => None | Ok(v) => Some(v) }))
          }
        })
        ->Promise.then(optVbp => {
          switch optVbp {
          | None => Promise.resolve(None)
          | Some(vbp) => Bindings.Winax.WINAX_BINDING.get(_toComObject(vbp), "Count")
              ->Promise.then(r => Promise.resolve(switch r { | Error(_) => None | Ok(v) => Some(v) }))
          }
        })
        ->Promise.then(optCount => {
          switch optCount {
          | None => Promise.resolve(None)
          | Some(countVal) => {
              let count = switch countVal {
              | JSON.Number(x) => Float.toInt(x)
              | _ => 0
              }
              let rec find: (int) => Promise.t<option<ComInterfaces.comObject>> = (
                (i) => {
                  if i > count { Promise.resolve(None) }
                  else {
                    Bindings.Winax.WINAX_BINDING.get(app, "VBE")
                      ->Promise.then(r => Promise.resolve(switch r { | Error(_) => None | Ok(v) => Some(v) }))
                      ->Promise.then(optVbeObj => {
                        switch optVbeObj {
                        | None => find(i + 1)
                        | Some(vbeObj) => {
                            Bindings.Winax.WINAX_BINDING.get(_toComObject(vbeObj), "VBProjects")
                              ->Promise.then(r => Promise.resolve(switch r { | Error(_) => None | Ok(v) => Some(v) }))
                              ->Promise.then(optVbproj => {
                                switch optVbproj {
                                | None => find(i + 1)
                                | Some(vbproj) => {
                                    Bindings.Winax.WINAX_BINDING.invoke(_toComObject(vbproj), "Item", [ComInterfaces.VInt(i)])
                                      ->Promise.then(r => Promise.resolve(switch r { | Error(_) => None | Ok(v) => Some(v) }))
                                      ->Promise.then(optP => {
                                        switch optP {
                                        | None => find(i + 1)
                                        | Some(p) => Promise.resolve(Some(_toComObject(p)))
                                        }
                                      })
                                      ->Promise.catch(_ => find(i + 1))
                                  }
                                }
                              })
                              ->Promise.catch(_ => find(i + 1))
                          }
                        }
                      })
                      ->Promise.catch(_ => find(i + 1))
                  }
                }
              )
              find(1)
            }
          }
        })
        ->Promise.catch(_ => Promise.resolve(None))
    }
  }
)

// ---------------------------------------------------------------------------
// _getVbComponent — find a VBComponent by name in a VBProject
// ---------------------------------------------------------------------------

let _getVbComponent: (ComInterfaces.comObject, string) => Promise.t<option<ComInterfaces.comObject>> = (
  (proj, name) => {
    Bindings.Winax.WINAX_BINDING.get(proj, "VBComponents")
      ->Promise.then(result => {
        switch result {
        | Error(_) => Promise.resolve(None)
        | Ok(vbc) => Bindings.Winax.WINAX_BINDING.get(_toComObject(vbc), "Count")
          ->Promise.then(countResult => {
            let count = switch countResult {
            | Error(_) => 0
            | Ok(JSON.Number(x)) => Float.toInt(x)
            | Ok(_) => 0
            }
            let rec find: (int) => Promise.t<option<ComInterfaces.comObject>> = (
              (i) => {
                if i > count { Promise.resolve(None) }
                else {
                  Bindings.Winax.WINAX_BINDING.invoke(_toComObject(vbc), "Item", [ComInterfaces.VInt(i)])
                    ->Promise.then(compResult => {
                      switch compResult {
                      | Error(_) => find(i + 1)
                      | Ok(comp) => {
                          Bindings.Winax.WINAX_BINDING.get(_toComObject(comp), "Name")
                            ->Promise.then(nm => {
                              switch nm {
                              | Error(_) => find(i + 1)
                              | Ok(JSON.String(s)) if s == name => Promise.resolve(Some(_toComObject(comp)))
                              | Ok(_) => find(i + 1)
                              }
                            })
                            ->Promise.catch(_ => find(i + 1))
                        }
                      }
                    })
                    ->Promise.catch(_ => find(i + 1))
                }
              }
            )
            find(1)
          })
        }
      })
      ->Promise.catch(_ => Promise.resolve(None))
  }
)

// ---------------------------------------------------------------------------
// _tlWrap — capture → func → restore (in finally), non-fatal
// ---------------------------------------------------------------------------

let _tlWrap: (unit => Promise.t<'a>) => Promise.t<'a> = (
  (fn) => {
    TrustedLocations.capture()
      ->Promise.then(saved => {
        let locs = switch saved {
        | Ok(a) if Array.length(a) > 0 => Some(a)
        | _ => None
        }
        fn()
          ->Promise.then(r => {
            let restorer: Promise.t<unit> = switch locs {
      | Some(ls) => TrustedLocations.restore(ls)->Promise.then(_ok => Promise.resolve())
            | None => Promise.resolve()
            }
            restorer->Promise.then(_ => Promise.resolve(r))->Promise.catch(_ => Promise.resolve(r))
          })
          ->Promise.catch(e => {
            let restorer: Promise.t<unit> = switch locs {
      | Some(ls) => TrustedLocations.restore(ls)->Promise.then(_ok => Promise.resolve())->Promise.catch(_err => Promise.resolve())
            | None => Promise.resolve()
            }
      restorer->Promise.then(_ => Promise.reject(e))->Promise.catch(_ex => Promise.reject(e))
          })
      })
  }
)

// ---------------------------------------------------------------------------
// getModules — enumerate all VBA modules
// ---------------------------------------------------------------------------

let _getModules: ComInterfaces.sessionHandles => Promise.t<array<moduleInfo>> = (
  (handles) => {
    if !_connected(handles) { Promise.resolve([]) }
    else { Promise.resolve([]) }
  }
)

// ---------------------------------------------------------------------------
// getVbaCode — get VBA code from a module
// ---------------------------------------------------------------------------

let _getVbaCode: (ComInterfaces.sessionHandles, string) => Promise.t<string> = (
  (handles, _name) => {
    if !_connected(handles) { Promise.resolve("") }
    else { Promise.resolve("") }
  }
)

// ---------------------------------------------------------------------------
// setVbaCode — set VBA code in a module
// Wrapped in _tlWrap.
// New module: temp file + LoadFromText(5, name, path).
// Existing: DeleteLines + AddFromString.
// ---------------------------------------------------------------------------

let _writeTmp: string => Promise.t<string> = (
  (data: string) => {
    let tmpPath = NodeJs.Path.join2(
      NodeJs.Os.tmpdir(),
      "mcp_vba_" ++ Float.toString(Math.random())->String.split(".")->Array.get(1)->Option.getOr("") ++ ".txt"
    )
    let _enc = if NodeJs.Os.platform() == "win32" {
      "buffer"
    } else {
      "utf8"
    }
    let buf = NodeJs.Buffer.fromStringWithEncoding(data, NodeJs.StringEncoding.utf8)
    try {
      NodeJs.Fs.writeFileSync(tmpPath, buf)
      Promise.resolve(tmpPath)
    } catch {
      | _ => Promise.resolve("")
    }
  }
)

let _setVbaCode: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool> = (
  (handles, name, code) => {
    if !_connected(handles) { Promise.resolve(false) }
    else {
      let _do: unit => Promise.t<bool> = (
        () => {
          _getVbProject(handles)
            ->Promise.then(mb => {
              switch mb {
              | None => Promise.resolve(false)
              | Some(proj) => {
                  _getVbComponent(proj, name)
                    ->Promise.then(mc => {
                      switch mc {
                      | None => {
                          // New: temp file + LoadFromText(5, name, tmpPath)
                          let txt = "Attribute VB_Name = \"" ++ name ++ "\"\r\n" ++ code
                          _writeTmp(txt)
                            ->Promise.then(tmp => {
                              if tmp == "" { Promise.resolve(false) }
                              else {
                                let a = _app(handles)
                                Bindings.Winax.WINAX_BINDING.invoke(a, "LoadFromText", [ComInterfaces.VInt(_ACMODULE), ComInterfaces.VStr(name), ComInterfaces.VStr(tmp)])
                                  ->Promise.then(r => switch r { | Ok(_) => Promise.resolve(true) | Error(_) => Promise.resolve(false) })
                                  ->Promise.catch(_ => Promise.resolve(false))
                              }
                            })
                        }
                      | Some(comp) => {
                          Bindings.Winax.WINAX_BINDING.get(comp, "CodeModule")
                            ->Promise.then(r => Promise.resolve(switch r { | Error(_) => None | Ok(v) => Some(v) }))
                            ->Promise.then(optCm => {
                              switch optCm {
                              | None => Promise.resolve(false)
                              | Some(cm) => {
                                  Bindings.Winax.WINAX_BINDING.get(_toComObject(cm), "CountOfLines")
                                    ->Promise.then(r => Promise.resolve(switch r { | Error(_) => None | Ok(v) => Some(v) }))
                                    ->Promise.then(optN => {
                                      let lines = switch optN {
                                      | None => 0
                                      | Some(JSON.Number(x)) => Float.toInt(x)
                                      | Some(_) => 0
                                      }
                                      if lines > 0 {
                                        Bindings.Winax.WINAX_BINDING.invoke(_toComObject(cm), "DeleteLines", [ComInterfaces.VInt(1), ComInterfaces.VInt(lines)])
                                          ->Promise.then(r => Promise.resolve(switch r { | Error(_) => false | Ok(_) => true }))
                                          ->Promise.then(ok => {
                                            if !ok { Promise.resolve(false) }
                                            else {
                                              Bindings.Winax.WINAX_BINDING.invoke(_toComObject(cm), "AddFromString", [ComInterfaces.VStr(code)])
                                                ->Promise.then(r2 => Promise.resolve(switch r2 { | Ok(_) => true | Error(_) => false }))
                                                ->Promise.catch(_ => Promise.resolve(false))
                                            }
                                          })
                                          ->Promise.catch(_ => Promise.resolve(false))
                                      } else {
                                        Bindings.Winax.WINAX_BINDING.invoke(_toComObject(cm), "AddFromString", [ComInterfaces.VStr(code)])
                                          ->Promise.then(r => Promise.resolve(switch r { | Ok(_) => true | Error(_) => false }))
                                          ->Promise.catch(_ => Promise.resolve(false))
                                      }
                                    })
                                    ->Promise.catch(_ => Promise.resolve(false))
                                }
                              }
                            })
                            ->Promise.catch(_ => Promise.resolve(false))
                        }
                      }
                    })
                }
              }
            })
        }
      )
      _tlWrap(_do)
    }
  }
)

// ---------------------------------------------------------------------------
// addVbaProcedure — add a procedure to a module (wrapped in _tlWrap)
// ---------------------------------------------------------------------------

let _addVbaProcedure: (ComInterfaces.sessionHandles, string, string, string) => Promise.t<bool> = (
  (handles, name, proc, code) => {
    if !_connected(handles) { Promise.resolve(false) }
    else {
      let _do: unit => Promise.t<bool> = (
        () => {
          _getVbProject(handles)
            ->Promise.then(mb => {
              switch mb {
              | None => Promise.resolve(false)
              | Some(proj) => {
                  _getVbComponent(proj, name)
                    ->Promise.then(mc => {
                      switch mc {
                      | None => {
                          let txt = "Attribute VB_Name = \"" ++ name ++ "\"\r\n" ++ "Sub " ++ proc ++ "()\r\n" ++ code ++ "\r\nEnd Sub"
                          _writeTmp(txt)
                            ->Promise.then(tmp => {
                              if tmp == "" { Promise.resolve(false) }
                              else {
                                let a = _app(handles)
                                Bindings.Winax.WINAX_BINDING.invoke(a, "LoadFromText", [ComInterfaces.VInt(_ACMODULE), ComInterfaces.VStr(name), ComInterfaces.VStr(tmp)])
                                  ->Promise.then(r => switch r { | Ok(_) => Promise.resolve(true) | Error(_) => Promise.resolve(false) })
                                  ->Promise.catch(_ => Promise.resolve(false))
                              }
                            })
                        }
                      | Some(comp) => {
                          Bindings.Winax.WINAX_BINDING.get(comp, "CodeModule")
                            ->Promise.then(r => Promise.resolve(switch r { | Error(_) => None | Ok(v) => Some(v) }))
                            ->Promise.then(optCm => {
                              switch optCm {
                              | None => Promise.resolve(false)
                              | Some(cm) => {
                                  Bindings.Winax.WINAX_BINDING.invoke(_toComObject(cm), "AddFromString", [ComInterfaces.VStr(code)])
                                    ->Promise.then(r => Promise.resolve(switch r { | Ok(_) => true | Error(_) => false }))
                                    ->Promise.catch(_ => Promise.resolve(false))
                                }
                              }
                            })
                            ->Promise.catch(_ => Promise.resolve(false))
                        }
                      }
                    })
                }
              }
            })
        }
      )
      _tlWrap(_do)
    }
  }
)

// ---------------------------------------------------------------------------
// deleteModule — remove a VBA module
// ---------------------------------------------------------------------------

let _deleteModule: (ComInterfaces.sessionHandles, string) => Promise.t<bool> = (
  (handles, name) => {
    if !_connected(handles) { Promise.resolve(false) }
    else {
      _getVbProject(handles)
        ->Promise.then(mb => {
          switch mb {
          | None => Promise.resolve(false)
          | Some(proj) => {
              _getVbComponent(proj, name)
                ->Promise.then(mc => {
                  switch mc {
                  | None => Promise.resolve(false)
                  | Some(_comp) => {
                      Bindings.Winax.WINAX_BINDING.get(proj, "VBComponents")
                        ->Promise.then(r => Promise.resolve(switch r { | Error(_) => None | Ok(v) => Some(v) }))
                        ->Promise.then(optVbc => {
                          switch optVbc {
                          | None => Promise.resolve(false)
                          | Some(vbc) => {
                              Bindings.Winax.WINAX_BINDING.invoke(_toComObject(vbc), "Remove", [])
                                ->Promise.then(_ => Promise.resolve(true))
                                ->Promise.catch(_ => Promise.resolve(false))
                            }
                          }
                        })
                        ->Promise.catch(_ => Promise.resolve(false))
                    }
                  }
                })
            }
          }
        })
    }
  }
)

// ---------------------------------------------------------------------------
// createModule — create a new VBA module
// ---------------------------------------------------------------------------

let _createModule: (ComInterfaces.sessionHandles, string, ~moduleType: int=?) => Promise.t<bool> = (
  (handles, name, ~moduleType=?) => {
    let mt = switch moduleType { | Some(t) => t | None => _VBE_STD_MODULE }
    if !_connected(handles) { Promise.resolve(false) }
    else {
      _getVbProject(handles)
        ->Promise.then(mb => {
          switch mb {
          | None => Promise.resolve(false)
          | Some(proj) => {
              Bindings.Winax.WINAX_BINDING.get(proj, "VBComponents")
                ->Promise.then(result => {
                  switch result {
                  | Error(_) => Promise.resolve(false)
                  | Ok(vbc) => {
                      Bindings.Winax.WINAX_BINDING.invoke(_toComObject(vbc), "Add", [ComInterfaces.VInt(mt)])
                        ->Promise.then(compResult => {
                          switch compResult {
                          | Error(_) => Promise.resolve(false)
                          | Ok(comp) => {
                              Bindings.Winax.WINAX_BINDING.set(_toComObject(comp), "Name", ComInterfaces.VStr(name))
                                ->Promise.then(r => switch r { | Ok(_) => Promise.resolve(true) | Error(_) => Promise.resolve(false) })
                                ->Promise.catch(_ => Promise.resolve(false))
                            }
                          }
                        })
                        ->Promise.catch(_ => Promise.resolve(false))
                    }
                  }
                })
                ->Promise.catch(_ => Promise.resolve(false))
            }
          }
        })
    }
  }
)

// ---------------------------------------------------------------------------
// renameModule — rename an existing module
// ---------------------------------------------------------------------------

let _renameModule: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool> = (
  (handles, oldName, newName) => {
    if !_connected(handles) { Promise.resolve(false) }
    else {
      _getVbProject(handles)
        ->Promise.then(mb => {
          switch mb {
          | None => Promise.resolve(false)
          | Some(proj) => {
              _getVbComponent(proj, oldName)
                ->Promise.then(mc => {
                  switch mc {
                  | None => Promise.resolve(false)
                  | Some(comp) => {
                      Bindings.Winax.WINAX_BINDING.set(comp, "Name", ComInterfaces.VStr(newName))
                        ->Promise.then(r => switch r { | Ok(_) => Promise.resolve(true) | Error(_) => Promise.resolve(false) })
                        ->Promise.catch(_ => Promise.resolve(false))
                    }
                  }
                })
            }
          }
        })
    }
  }
)

// ---------------------------------------------------------------------------
// moduleExists — check via CurrentProject.AllModules (0-based DAO)
// ---------------------------------------------------------------------------

let _moduleExists: (ComInterfaces.sessionHandles, string) => Promise.t<bool> = (
  (handles, name) => {
    if !_connected(handles) { Promise.resolve(false) }
    else {
      let app = _app(handles)
      Bindings.Winax.WINAX_BINDING.get(app, "CurrentProject")
        ->Promise.then(cpResult => {
          switch cpResult {
          | Error(_) => Promise.resolve(false)
          | Ok(cp) => {
              Bindings.Winax.WINAX_BINDING.get(_toComObject(cp), "AllModules")
                ->Promise.then(allModsResult => {
                  switch allModsResult {
                  | Error(_) => Promise.resolve(false)
                  | Ok(allMods) => {
                      Bindings.Winax.WINAX_BINDING.get(_toComObject(allMods), "Count")
                        ->Promise.then(nResult => {
                          let count = switch nResult {
                          | Ok(JSON.Number(x)) => Float.toInt(x)
                          | _ => 0
                          }
                          let rec loop: (int) => Promise.t<bool> = (
                            (i) => {
                              if i >= count { Promise.resolve(false) }
                              else {
                                Bindings.Winax.WINAX_BINDING.invoke(_toComObject(allMods), "Item", [ComInterfaces.VInt(i)])
                                  ->Promise.then(modResult => {
                                    switch modResult {
                                    | Error(_) => loop(i + 1)
                                    | Ok(mod) => {
                      Bindings.Winax.WINAX_BINDING.get(_toComObject(mod), "Name")
                        ->Promise.then(nmResult => {
                          switch nmResult {
                          | Ok(JSON.String(s)) if s == name => Promise.resolve(true)
                          | _ => loop(i + 1)
                          }
                                          })
                                          ->Promise.catch(_ => loop(i + 1))
                                      }
                                    }
                                  })
                                  ->Promise.catch(_ => loop(i + 1))
                              }
                            }
                          )
                          loop(0)
                        })
                        ->Promise.catch(_ => Promise.resolve(false))
                    }
                  }
                })
                ->Promise.catch(_ => Promise.resolve(false))
            }
          }
        })
        ->Promise.catch(_ => Promise.resolve(false))
    }
  }
)

// ---------------------------------------------------------------------------
// compileVba — compile VBA with RunCommand IDs [301, 206, 317, 232]
// Wrapped in _tlWrap. Returns {success, error}.
// ---------------------------------------------------------------------------

let _compileVba: ComInterfaces.sessionHandles => Promise.t<compileResult> = (
  (handles) => {
    if !_connected(handles) {
      Promise.resolve({success: false, error: Some("Not connected")})
    } else {
      let _do: unit => Promise.t<compileResult> = () => {
        let app = _app(handles)
        let rec tryCompile: (int) => Promise.t<compileResult> = (idx) => {
          if idx >= Array.length(_COMPILE_CMD_IDS) {
            Promise.resolve({
              success: false,
              error: Some("Could not find working compile command for this Access version"),
            })
          } else {
            let cid = switch Array.get(_COMPILE_CMD_IDS, idx) {
            | Some(c) => c
            | None => -1
            }
            Bindings.Winax.WINAX_BINDING.get(app, "DoCmd")
              ->Promise.then(docmdR => {
                switch docmdR {
                | Error(_) =>
                  Promise.resolve({success: false, error: Some("Cannot get DoCmd")})
                | Ok(docmd) =>
                  Bindings.Winax.WINAX_BINDING.invoke(
                    _toComObject(docmd),
                    "RunCommand",
                    [ComInterfaces.VInt(cid)],
                  )->Promise.then(r =>
                    switch r {
                    | Ok(_) => Promise.resolve({success: true, error: None})
                    | Error(_) => tryCompile(idx + 1)
                    }
                  )
                }
              })
              ->Promise.catch(_ => tryCompile(idx + 1))
          }
        }
        tryCompile(0)
      }
      _tlWrap(_do)
        ->Promise.then(r => Promise.resolve(r))
        ->Promise.catch(e => {
          let msg = _exnMsg(e)
          Promise.resolve({success: false, error: Some(msg)})
        })
    }
  }
)

// ---------------------------------------------------------------------------
// executeVba — run a VBA function via Application.Run
// ---------------------------------------------------------------------------

let _executeVba: (ComInterfaces.sessionHandles, string, array<JSON.t>) => Promise.t<option<JSON.t>> = (
  (handles, fnName, _args) => {
    if !_connected(handles) { Promise.resolve(None) }
    else {
      let app = _app(handles)
      Bindings.Winax.WINAX_BINDING.invoke(app, "Run", [ComInterfaces.VStr(fnName)])
        ->Promise.then(r => switch r { | Ok(v) => Promise.resolve(Some(v)) | Error(_) => Promise.resolve(None) })
        ->Promise.catch(_ => Promise.resolve(None))
    }
  }
)

// ---------------------------------------------------------------------------
// vbaListProcedures — list procedures in a module
// ---------------------------------------------------------------------------

let _vbaListProcedures: (ComInterfaces.sessionHandles, string) => Promise.t<array<vbProcedureInfo>> = (
  (handles, name) => {
    if !_connected(handles) { Promise.resolve([]) }
    else {
      _getVbProject(handles)
        ->Promise.then(mb => {
          switch mb {
          | None => Promise.resolve([])
          | Some(proj) => {
              _getVbComponent(proj, name)
                ->Promise.then(mc => {
                  switch mc {
                  | None => Promise.resolve([])
                  | Some(comp) => {
                      Bindings.Winax.WINAX_BINDING.get(comp, "CodeModule")
                        ->Promise.then(cmResult => {
                          switch cmResult {
                          | Error(_) => Promise.resolve([])
                          | Ok(cm) => {
                              let cmObj = _toComObject(cm)
                              Bindings.Winax.WINAX_BINDING.get(cmObj, "CountOfLines")
                                ->Promise.then(nResult => {
                                  let total = switch nResult {
                                  | Ok(JSON.Number(x)) => Float.toInt(x)
                                  | _ => 0
                                  }
                                  if total == 0 { Promise.resolve([]) }
                                  else {
                                    let rec gather: (int, array<vbProcedureInfo>) => Promise.t<array<vbProcedureInfo>> = (
                                      (line, acc) => {
                                        if line > total { Promise.resolve(acc) }
                                        else {
                                          Bindings.Winax.WINAX_BINDING.invoke(cmObj, "ProcOfLine", [ComInterfaces.VInt(line), ComInterfaces.VInt(0)])
                                            ->Promise.then(nmR => {
                                              let pName = switch nmR {
                                              | Ok(JSON.String(s)) => s
                                              | _ => ""
                                              }
                                              if pName == "" { gather(line + 1, acc) }
                                              else {
                                                let seen = {
                                                  let rec chk: (array<vbProcedureInfo>, int) => bool = (
                                                    (arr, i) => {
                                                      if i >= Array.length(arr) { false }
                                                      else {
                                                        let item = Array.get(arr, i)
                                                        switch item {
                                                        | Some(info) => info.name == pName || chk(arr, i + 1)
                                                        | None => false
                                                        }
                                                      }
                                                    }
                                                  )
                                                  chk(acc, 0)
                                                }
                                                if seen { gather(line + 1, acc) }
                                                else {
                                                  Bindings.Winax.WINAX_BINDING.invoke(cmObj, "ProcKind", [ComInterfaces.VInt(line), ComInterfaces.VInt(0)])
                                                    ->Promise.then(kR => {
                                                      let k = switch kR {
                                                      | Ok(JSON.Number(x)) => Float.toInt(x)
                                                      | _ => 0
                                                      }
                                                      let pt = if k == 0 { "Sub" } else if k == 1 { "Function" } else { "Property" }
                                                      Bindings.Winax.WINAX_BINDING.invoke(cmObj, "ProcStartLine", [ComInterfaces.VStr(pName), ComInterfaces.VInt(0)])
                                                        ->Promise.then(sR => {
                                                          let sl = switch sR {
                                                          | Ok(JSON.Number(x)) => Float.toInt(x)
                                                          | _ => line
                                                          }
                                                          Bindings.Winax.WINAX_BINDING.invoke(cmObj, "ProcCountLines", [ComInterfaces.VStr(pName), ComInterfaces.VInt(0)])
                                                            ->Promise.then(cR => {
                                                              let lc = switch cR {
                                                              | Ok(JSON.Number(x)) => Float.toInt(x)
                                                              | _ => 1
                                                              }
                                                              let info: vbProcedureInfo = {name: pName, procType: pt, startLine: sl, lineCount: lc}
                                                              gather(line + 1, Array.concat(acc, [info]))
                                                            })
                                                            ->Promise.catch(_ => gather(line + 1, acc))
                                                        })
                                                        ->Promise.catch(_ => gather(line + 1, acc))
                                                    })
                                                    ->Promise.catch(_ => gather(line + 1, acc))
                                                }
                                              }
                                            })
                                            ->Promise.catch(_ => gather(line + 1, acc))
                                        }
                                      }
                                    )
                                    gather(1, [])
                                  }
                                })
                                ->Promise.catch(_ => Promise.resolve([]))
                            }
                          }
                        })
                        ->Promise.catch(_ => Promise.resolve([]))
                    }
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

// ---------------------------------------------------------------------------
// saveDatabase — save all standard modules via DoCmd.Save
// ---------------------------------------------------------------------------

let _saveDatabase: ComInterfaces.sessionHandles => Promise.t<saveResult> = (
  (handles) => {
    if !_connected(handles) { Promise.resolve({success: false, savedModules: 0, errors: []}) }
    else {
      _getVbProject(handles)
        ->Promise.then(mb => {
          switch mb {
          | None => Promise.resolve({success: false, savedModules: 0, errors: ["No VBA project"]})
          | Some(proj) => {
              Bindings.Winax.WINAX_BINDING.get(proj, "VBComponents")
                ->Promise.then(vbcResult => {
                  switch vbcResult {
                  | Error(_) => Promise.resolve({success: false, savedModules: 0, errors: ["Cannot get VBComponents"]})
                  | Ok(vbc) => {
                      let vbcObj = _toComObject(vbc)
                      Bindings.Winax.WINAX_BINDING.get(vbcObj, "Count")
                        ->Promise.then(nResult => {
                          let cnt = switch nResult {
                          | Ok(JSON.Number(x)) => Float.toInt(x)
                          | _ => 0
                          }
                          let app = _app(handles)
                          let rec loop: (int, int, array<string>) => Promise.t<saveResult> = (
                            (i, saved, errs) => {
                              if i > cnt { Promise.resolve({success: Array.length(errs) == 0, savedModules: saved, errors: errs}) }
                              else {
                                Bindings.Winax.WINAX_BINDING.invoke(vbcObj, "Item", [ComInterfaces.VInt(i)])
                                  ->Promise.then(compResult => {
                                    switch compResult {
                                    | Error(_) => loop(i + 1, saved, errs)
                                    | Ok(comp) => {
                                        let compObj = _toComObject(comp)
                                        Bindings.Winax.WINAX_BINDING.get(compObj, "Type")
                                          ->Promise.then(tResult => {
                                            let mt = switch tResult {
                                            | Ok(JSON.Number(x)) => Float.toInt(x)
                                            | _ => 0
                                            }
                                            if mt != _VBE_STD_MODULE { loop(i + 1, saved, errs) }
                                            else {
                                              Bindings.Winax.WINAX_BINDING.get(compObj, "Name")
                                                ->Promise.then(nmResult => {
                                                  let mName = switch nmResult {
                                                  | Ok(JSON.String(s)) => s
                                                  | _ => ""
                                                  }
                                                  Bindings.Winax.WINAX_BINDING.get(app, "DoCmd")
                                                    ->Promise.then(docmdResult => {
                                                      switch docmdResult {
                                                      | Error(_) => loop(i + 1, saved, Array.concat(errs, [mName ++ ": Cannot get DoCmd"]))
                                                      | Ok(docmd) => {
                                                          let docmdObj = _toComObject(docmd)
                                                          Bindings.Winax.WINAX_BINDING.invoke(docmdObj, "Save", [ComInterfaces.VInt(_ACMODULE), ComInterfaces.VStr(mName)])
                                                            ->Promise.then(_ => loop(i + 1, saved + 1, errs))
                                                            ->Promise.catch(e => {
                                                              let msg = _exnMsg(e)
                                                              loop(i + 1, saved, Array.concat(errs, [mName ++ ": " ++ msg]))
                                                            })
                                                        }
                                                      }
                                                    })
                                                    ->Promise.catch(e => {
                                                      let msg = _exnMsg(e)
                                                      loop(i + 1, saved, Array.concat(errs, [mName ++ ": " ++ msg]))
                                                    })
                                                })
                                                ->Promise.catch(e => {
                                                  let msg = _exnMsg(e)
                                                  loop(i + 1, saved, Array.concat(errs, [msg]))
                                                })
                                            }
                                          })
                                          ->Promise.catch(e => {
                                            let msg = _exnMsg(e)
                                            loop(i + 1, saved, Array.concat(errs, [msg]))
                                          })
                                      }
                                    }
                                  })
                                  ->Promise.catch(e => {
                                    let msg = _exnMsg(e)
                                    loop(i + 1, saved, Array.concat(errs, [msg]))
                                  })
                              }
                            }
                          )
                          loop(1, 0, [])
                        })
                        ->Promise.catch(_ => Promise.resolve({success: false, savedModules: 0, errors: ["Cannot enumerate components"]}))
                    }
                  }
                })
                ->Promise.catch(_ => Promise.resolve({success: false, savedModules: 0, errors: ["Cannot enumerate components"]}))
            }
          }
        })
        ->Promise.catch(_ => Promise.resolve({success: false, savedModules: 0, errors: ["Cannot get VBA project"]}))
    }
  }
)
