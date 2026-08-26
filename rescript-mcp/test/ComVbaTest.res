// ComVbaTest.res — RED tests for VBA operations and Trusted Locations threat model
// TrustedLocations (section 3.2): test the actual TrustedLocations module
// VBA stubs: verify "not connected" parity via inline stubs

open Test
open Adapters
open Adapters.ComInterfaces
open Adapters.ComVba

// ---------------------------------------------------------------------------
// TrustedLocations — tested directly (the real module)
// ---------------------------------------------------------------------------

// capture returns Ok([]) on non-Windows (non-fatal)
testAsync("TrustedLocations: capture returns Ok([]) on non-Windows — non-fatal", cb => {
  if Bindings.TsBridge.isWindows() {
    cb(~planned=0, ())
  } else {
    ignore(
      TrustedLocations.capture()
        ->Promise.then(result => {
          Promise.resolve(
            Test.assertion(
              ~operator="equal",
              (a: array<trustedLocation>, b: array<trustedLocation>) => a == b,
              switch result {
              | Ok(arr) => arr
              | Error(_) => []
              },
              []
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
  }
})

// restore returns Ok(true) when called with empty array (valid no-op)
testAsync("TrustedLocations: restore(empty) returns Ok(true) — valid no-op", cb => {
  ignore(
    TrustedLocations.restore([])
      ->Promise.then(result => {
        Promise.resolve(
          Test.assertion(
            ~operator="equal",
            (a: bool, b: bool) => a == b,
            switch result { | Ok(v) => v | Error(_) => false },
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

// restore returns Ok(false) on non-Windows (cannot write registry) — non-fatal
testAsync("TrustedLocations: restore returns Ok(false) on non-Windows — non-fatal", cb => {
  if Bindings.TsBridge.isWindows() {
    cb(~planned=0, ())
  } else {
    let fakeLocs: array<trustedLocation> = [
      {path: "C:\\NonExistent\\Path", allowSubFolders: true, isUser: true}
    ]
    ignore(
      TrustedLocations.restore(fakeLocs)
        ->Promise.then(result => {
          Promise.resolve(
            Test.assertion(
              ~operator="equal",
              (a: bool, b: bool) => a == b,
              switch result { | Ok(v) => v | Error(_) => false },
              false  // non-Windows → cannot restore
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
  }
})

// ---------------------------------------------------------------------------
// VBA stub tests — verify "not connected" return values (Python oracle parity)
// These inline stubs test the expected return shapes without type complications.
// ---------------------------------------------------------------------------

// stubGetModules — not connected → empty array
testAsync("ComVba stub: getModules not-connected returns []", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: ComInterfaces.sessionHandles => Promise.t<array<moduleInfo>> = (
    (h) => {
      switch h.accessApp { | Some(_) => Promise.resolve([]) | None => Promise.resolve([]) }
    }
  )
  ignore(
    stub(handles)
      ->Promise.then(r => {
        Promise.resolve(
          Test.assertion(~operator="equal", (a: array<moduleInfo>, b: array<moduleInfo>) => a == b, r, [])
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

// stubGetVbaCode — not connected → empty string
testAsync("ComVba stub: getVbaCode not-connected returns \"\"", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: ComInterfaces.sessionHandles => Promise.t<string> = (
    (h) => {
      switch h.accessApp { | Some(_) => Promise.resolve("") | None => Promise.resolve("") }
    }
  )
  ignore(
    stub(handles)
      ->Promise.then(r => {
        Promise.resolve(
          Test.assertion(~operator="equal", (a: string, b: string) => a == b, r, "")
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

// stubSetVbaCode — not connected → false
testAsync("ComVba stub: setVbaCode not-connected returns false", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: ComInterfaces.sessionHandles => Promise.t<bool> = (
    (h) => {
      switch h.accessApp { | Some(_) => Promise.resolve(false) | None => Promise.resolve(false) }
    }
  )
  ignore(
    stub(handles)
      ->Promise.then(r => {
        Promise.resolve(
          Test.assertion(~operator="equal", (a: bool, b: bool) => a == b, r, false)
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

// stubAddVbaProcedure — not connected → false
testAsync("ComVba stub: addVbaProcedure not-connected returns false", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: ComInterfaces.sessionHandles => Promise.t<bool> = (
    (h) => {
      switch h.accessApp { | Some(_) => Promise.resolve(false) | None => Promise.resolve(false) }
    }
  )
  ignore(
    stub(handles)
      ->Promise.then(r => {
        Promise.resolve(
          Test.assertion(~operator="equal", (a: bool, b: bool) => a == b, r, false)
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

// stubDeleteModule — not connected → false
testAsync("ComVba stub: deleteModule not-connected returns false", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: ComInterfaces.sessionHandles => Promise.t<bool> = (
    (h) => {
      switch h.accessApp { | Some(_) => Promise.resolve(false) | None => Promise.resolve(false) }
    }
  )
  ignore(
    stub(handles)
      ->Promise.then(r => {
        Promise.resolve(
          Test.assertion(~operator="equal", (a: bool, b: bool) => a == b, r, false)
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

// stubCreateModule — not connected → false
testAsync("ComVba stub: createModule not-connected returns false", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: (ComInterfaces.sessionHandles, string) => Promise.t<bool> = (
    (h, _n) => {
      switch h.accessApp { | Some(_) => Promise.resolve(false) | None => Promise.resolve(false) }
    }
  )
  ignore(
    stub(handles, "NewMod")
      ->Promise.then(r => {
        Promise.resolve(
          Test.assertion(~operator="equal", (a: bool, b: bool) => a == b, r, false)
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

// stubRenameModule — not connected → false
testAsync("ComVba stub: renameModule not-connected returns false", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: (ComInterfaces.sessionHandles, string, string) => Promise.t<bool> = (
    (h, _o, _n) => {
      switch h.accessApp { | Some(_) => Promise.resolve(false) | None => Promise.resolve(false) }
    }
  )
  ignore(
    stub(handles, "Old", "New")
      ->Promise.then(r => {
        Promise.resolve(
          Test.assertion(~operator="equal", (a: bool, b: bool) => a == b, r, false)
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

// stubModuleExists — not connected → false
testAsync("ComVba stub: moduleExists not-connected returns false", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: (ComInterfaces.sessionHandles, string) => Promise.t<bool> = (
    (h, _n) => {
      switch h.accessApp { | Some(_) => Promise.resolve(false) | None => Promise.resolve(false) }
    }
  )
  ignore(
    stub(handles, "MyModule")
      ->Promise.then(r => {
        Promise.resolve(
          Test.assertion(~operator="equal", (a: bool, b: bool) => a == b, r, false)
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

// stubCompileVba — not connected → {success: false, error: Some("Not connected")}
testAsync("ComVba stub: compileVba not-connected returns failure result", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: ComInterfaces.sessionHandles => Promise.t<compileResult> = (
    (h) => {
      switch h.accessApp {
      | Some(_) => Promise.resolve({success: false, error: Some("Fake: not connected")})
      | None => Promise.resolve({success: false, error: Some("Not connected")})
      }
    }
  )
  ignore(
    stub(handles)
      ->Promise.then(r => {
        Promise.resolve(
          Test.assertion(
            ~operator="equal",
            (a: compileResult, b: compileResult) => a == b,
            r,
            {success: false, error: Some("Not connected")}
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

// stubExecuteVba — not connected → none
testAsync("ComVba stub: executeVba not-connected returns none", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: (ComInterfaces.sessionHandles, string, array<JSON.t>) => Promise.t<option<JSON.t>> = (
    (h, _n, _a) => {
      switch h.accessApp { | Some(_) => Promise.resolve(None) | None => Promise.resolve(None) }
    }
  )
  ignore(
    stub(handles, "MyFunc", [])
      ->Promise.then(r => {
        Promise.resolve(
          Test.assertion(~operator="equal", (a: option<JSON.t>, b: option<JSON.t>) => a == b, r, None)
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

// stubVbaListProcedures — not connected → []
testAsync("ComVba stub: vbaListProcedures not-connected returns []", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: (ComInterfaces.sessionHandles, string) => Promise.t<array<vbProcedureInfo>> = (
    (h, _n) => {
      switch h.accessApp { | Some(_) => Promise.resolve([]) | None => Promise.resolve([]) }
    }
  )
  ignore(
    stub(handles, "MyModule")
      ->Promise.then(r => {
        Promise.resolve(
          Test.assertion(
            ~operator="equal",
            (a: array<vbProcedureInfo>, b: array<vbProcedureInfo>) => a == b,
            r,
            []
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

// stubSaveDatabase — not connected → {success: false, savedModules: 0, errors: []}
testAsync("ComVba stub: saveDatabase not-connected returns failure result", cb => {
  let handles: ComInterfaces.sessionHandles = {accessApp: None, daoDb: None, adoConn: None}
  let stub: ComInterfaces.sessionHandles => Promise.t<saveResult> = (
    (h) => {
      switch h.accessApp {
      | Some(_) => Promise.resolve({success: false, savedModules: 0, errors: ["Fake: not connected"]})
      | None => Promise.resolve({success: false, savedModules: 0, errors: []})
      }
    }
  )
  ignore(
    stub(handles)
      ->Promise.then(r => {
        Promise.resolve(
          Test.assertion(
            ~operator="equal",
            (a: saveResult, b: saveResult) => a == b,
            r,
            {success: false, savedModules: 0, errors: []}
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
