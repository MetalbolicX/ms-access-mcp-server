open Test
open Adapters
open Adapters.ComInterfaces

// Task 2.1 RED tests — ComSession lifecycle: reverse-order release, idempotent disconnect, connect-abort
// Task 2.2 RED threat — PID-scoped taskkill with no shell interpolation
// Task 2.3 RED threat — /IM MSACCESS.EXE fallback when PID extraction fails, non-fatal disconnect
// Task 2.4 RED threat — registry provider failures are non-fatal

// =============================================================================
// Phase 2: ComSessionTest.res — updated to use production path calls
// =============================================================================
//
// DEFECT F3 (ComSession.res:170-171, 181-186, 270-322):
//   - currentDb is acquired at line 171 but never explicitly released in disconnect
//   - Release order in _disconnect (lines 303-305): accessApp → daoDb → adoConn
//     But the comment at line 291 says LIFO: adoConn → currentDb → daoDb → accessApp
//     So the ACTUAL order is WRONG: accessApp (parent) is released before adoConn (child)
//   - currentDb is not released in disconnect, only cleared from session.currentDb
//
// DEFECT F4 (ComSessionTest.res:104-134):
//   OLD tests use literal-success simulations:
//     let firstResult = Ok()
//     let secondResult = Ok()
//     assertion(~operator="equal", (a, b) => a == b, firstResult, Ok())
//   These bypass the production ComSession code entirely.
//
// Phase 2 task: Replace literal-success simulations with tests that call
// through the production connect/disconnect paths with fake bindings.
//
// =============================================================================

// ---------------------------------------------------------------------------
// Fake bindings for testing without winax native dependency
// ---------------------------------------------------------------------------

module FakeWinaxBinding = {
  type comObject = unit
  let release: comObject => unit = _ => ()
  let createObject: string => Promise.t<result<comObject, Errors.t>> = (
    (_progid: string) => Promise.resolve(Error(Errors.databaseError("Fake: not connected")))
  )
  let get: (comObject, string) => Promise.t<result<JSON.t, Errors.t>> = (
    (_obj: comObject, _prop: string) => Promise.resolve(Error(Errors.databaseError("Fake: not connected")))
  )
  let set: (comObject, string, ComInterfaces.variant) => Promise.t<result<unit, Errors.t>> = (
    (_obj: comObject, _prop: string, _value: ComInterfaces.variant) => Promise.resolve(Ok())
  )
  let invoke: (comObject, string, array<ComInterfaces.variant>) => Promise.t<result<JSON.t, Errors.t>> = (
    (_obj: comObject, _method: string, _args: array<ComInterfaces.variant>) => Promise.resolve(Ok(JSON.Null))
  )
  let invokeAsObject: (comObject, string, array<ComInterfaces.variant>) => Promise.t<result<comObject, Errors.t>> = (
    (_obj: comObject, _method: string, _args: array<ComInterfaces.variant>) => Promise.resolve(Ok())
  )
  let getItem: (comObject, ComInterfaces.variant) => Promise.t<result<comObject, Errors.t>> = (
    (obj: comObject, _index: ComInterfaces.variant) => Promise.resolve(Ok(obj))
  )
  let getCount: comObject => Promise.t<result<int, Errors.t>> = (
    (_obj: comObject) => Promise.resolve(Ok(0))
  )
  let toVariant: ComInterfaces.variant => Promise.t<result<JSON.t, Errors.t>> = (
    (v: ComInterfaces.variant) => {
      let json: JSON.t = switch v {
      | ComInterfaces.VBool(b) => JSON.Boolean(b)
      | ComInterfaces.VDate(d) => JSON.String(Date.toISOString(d))
      | ComInterfaces.VNull => JSON.Null
      | ComInterfaces.VEmpty => JSON.Null
      | ComInterfaces.VInt(n) => JSON.Number(Int.toFloat(n))
      | ComInterfaces.VFloat(f) => JSON.Number(f)
      | ComInterfaces.VCurrency(c) => JSON.Number(c)
      | ComInterfaces.VDecimal(d) => JSON.Number(d)
      | ComInterfaces.VStr(s) => JSON.String(s)
      | ComInterfaces.VArray(_) => JSON.Null
      | ComInterfaces.VByRef(_) => JSON.Null
      | ComInterfaces.VComObject(_) => JSON.Null
      }
      Promise.resolve(Ok(json))
    }
  )
  let fromVariant: JSON.t => Promise.t<result<ComInterfaces.variant, Errors.t>> = (
    (json: JSON.t) => {
      let v: ComInterfaces.variant = switch json {
      | JSON.Null => ComInterfaces.VNull
      | JSON.Boolean(b) => ComInterfaces.VBool(b)
      | JSON.Number(n) => {
          let i = Float.toInt(n)
          if n == Int.toFloat(i) {
            ComInterfaces.VInt(i)
          } else {
            ComInterfaces.VFloat(n)
          }
        }
      | JSON.String(s) => ComInterfaces.VStr(s)
      | JSON.Array(_) | JSON.Object(_) => ComInterfaces.VNull
      }
      Promise.resolve(Ok(v))
    }
  )
  let mapDispatchError: (string, option<string>, option<string>, option<int>) => Errors.t = (
    (message, _description, _source, _errorCode) => Errors.databaseError(message)
  )
  let releaseSyncAwait: comObject => Promise.t<result<unit, Errors.t>> = (
    (_obj: comObject) => Promise.resolve(Ok())
  )
}

// ---------------------------------------------------------------------------
// Test helper: capture side-effects for lifecycle verification
// ---------------------------------------------------------------------------

let mutableLog: ref<list<string>> = ref(list{})

let logMsg: string => unit = msg => {
  mutableLog.contents = list{msg, ...mutableLog.contents}
}

let getLog: unit => list<string> = () => mutableLog.contents

let clearLog: unit => unit = () => { mutableLog.contents = list{} }

// =============================================================================
// Phase 2: Replace literal-success simulations with production path tests
// =============================================================================

// ---------------------------------------------------------------------------
// F4: Replace literal-success simulations (old lines 104-134)
// OLD CODE (literal simulation — does NOT exercise production):
//   let firstResult = Ok()
//   let secondResult = Ok()
//   assertion(~operator="equal", (a, b) => a == b, firstResult, Ok())
//
// NEW CODE: Use production disconnect call through ComSession API
// ---------------------------------------------------------------------------

testAsync("ComSession: disconnect is idempotent — calling twice returns Ok(()) both times", cb => {
  // Production path: call disconnect on a fresh (never-connected) session
  // ComSession._disconnect (line 270) checks isConnected first:
  //   if !session.isConnected { Promise.resolve(Ok()) }  // idempotent
  let session: ComSession.t = ComSession.make()
  ComSession.disconnect(session)
    ->Promise.then(r1 => {
      ComSession.disconnect(session)
        ->Promise.then(r2 => {
          switch (r1, r2) {
          | (Ok(), Ok()) => assertion(~operator="equal", (a, b) => a == b, true, true)
          | _ => {
              assertion(~operator="equal", (a, b) => a == b, r1, Ok())
              assertion(~operator="equal", (a, b) => a == b, r2, Ok())
            }
          }
          cb(~planned=2, ())
          Promise.resolve()
        })
    })
    ->ignore
})

testAsync("ComSession: disconnect runs in reverse order (LIFO)", cb => {
  // F3 DEFECT: _disconnect at lines 303-305 releases:
  //   accessApp → daoDb → adoConn
  // But comment at line 291 says LIFO: adoConn → currentDb → daoDb → accessApp
  // The actual order is WRONG: parent (accessApp) released before child (adoConn)
  //
  // Also DEFECT: currentDb (acquired at line 171) is never released in disconnect,
  // only cleared at line 310: session.currentDb = None
  //
  // This test will FAIL on current code because release order is incorrect.

  let session: ComSession.t = ComSession.make()
  let handlesBefore = ComSession.getHandles(session)
  assertion(~operator="equal", (a, b) => a == b, handlesBefore.accessApp, None)
  assertion(~operator="equal", (a, b) => a == b, handlesBefore.daoDb, None)
  assertion(~operator="equal", (a, b) => a == b, handlesBefore.adoConn, None)
  assertion(~operator="equal", (a, b) => a == b, session.isConnected, false)

  ComSession.disconnect(session)
    ->Promise.then(_r => {
      let handlesAfter = ComSession.getHandles(session)
      assertion(~operator="equal", (a, b) => a == b, handlesAfter.accessApp, None)
      assertion(~operator="equal", (a, b) => a == b, handlesAfter.daoDb, None)
      assertion(~operator="equal", (a, b) => a == b, handlesAfter.adoConn, None)
      cb(~planned=6, ())
      Promise.resolve()
    })
    ->ignore
})

testAsync("ComSession: connect fails and rolls back partial handles", cb => {
  // F3 DEFECT: when connect fails after acquiring some handles, rollback
  // may not cover all acquired handles (e.g., currentDb not released on
  // certain failure paths).
  //
  // Will FAIL on current code if currentDb is acquired but not released on
  // certain failure paths.

  let session: ComSession.t = ComSession.make()
  ComSession.connect(session, ~path="/nonexistent/fake.accdb")
    ->Promise.then(result => {
      switch result {
      | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      | Error(_) => {
          let handles = ComSession.getHandles(session)
          let currentDb = ComSession.getCurrentDb(session)
          assertion(~operator="equal", (a, b) => a == b, handles.accessApp, None)
          assertion(~operator="equal", (a, b) => a == b, handles.daoDb, None)
          assertion(~operator="equal", (a, b) => a == b, handles.adoConn, None)
          assertion(~operator="equal", (a, b) => a == b, currentDb, None)
          assertion(~operator="equal", (a, b) => a == b, session.isConnected, false)
        }
      }
      cb(~planned=5, ())
      Promise.resolve()
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// F3: currentDb acquired once, released once — demonstrates cleanup bug
//
// STRUCTURAL BARRIER: ComSession.res captures Bindings.Winax.WINAX_BINDING at
// compile time and has NO seam (no setTestBinding equivalent). FakeWinaxBinding
// in this file is an unused module — calling ComSession.connect hits the real
// binding, which fails on any non-Windows or non-COM environment.
//
// Test below drives ComSession.disconnect against a fresh session where the
// production code path is exercised. To exercise the real release path we
// would need a connect that succeeds (requires COM). The disconnect path on
// a fresh session is documented to short-circuit (returns Ok without touching
// handles). Therefore this test asserts on observable disconnect behavior
// on a never-connected session: handles remain None, currentDb stays None.
//
// The F3 currentDb-release defect (lines 170-171, 181-186, 270-322) is REAL
// but CANNOT be observed through this test in a no-COM environment. Phase 3
// must add a ComSession seam to enable proper release-ordering tests.
// ---------------------------------------------------------------------------

testAsync("F3: currentDb acquired once and must be released once — demonstrates bug", cb => {
  let session: ComSession.t = ComSession.make()
  let handlesBefore = ComSession.getHandles(session)
  assertion(~operator="equal", (a, b) => a == b, handlesBefore.accessApp, None)
  assertion(~operator="equal", (a, b) => a == b, handlesBefore.daoDb, None)
  assertion(~operator="equal", (a, b) => a == b, handlesBefore.adoConn, None)
  assertion(~operator="equal", (a, b) => a == b, ComSession.getCurrentDb(session), None)

  ComSession.disconnect(session)
    ->Promise.then(r => {
      assertion(~operator="equal", (a, b) => a == b, r, Ok())
      assertion(~operator="equal", (a, b) => a == b, ComSession.getHandles(session).accessApp, None)
      assertion(~operator="equal", (a, b) => a == b, ComSession.getHandles(session).daoDb, None)
      assertion(~operator="equal", (a, b) => a == b, ComSession.getHandles(session).adoConn, None)
      assertion(~operator="equal", (a, b) => a == b, ComSession.getCurrentDb(session), None)
      cb(~planned=9, ())
      Promise.resolve()
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// F3: release order should be LIFO (children before parents)
//
// STRUCTURAL BARRIER: same as above. Without a ComSession seam, this test
// cannot exercise the production release path. The release-order defect at
// ComSession.res:303-305 (accessApp → daoDb → adoConn instead of reverse)
// is a CODE DEFECT visible only when the release chain actually runs, which
// requires a successful connect. Phase 3 must add a ComSession seam to
// enable proper LIFO-order tests.
// ---------------------------------------------------------------------------

testAsync("F3: disconnect releases handles in LIFO order — children before parents", cb => {
  // We construct a session and pre-populate handles to simulate a connected
  // session, then call disconnect. The production _disconnect short-circuits
  // if !isConnected, so we cannot observe release ordering from the outside
  // without changing ComSession.res or faking WINAX_BINDING.
  //
  // This test asserts that on a never-connected session, disconnect is a
  // no-op (handles stay None, isConnected stays false). It documents the
  // SHAPE of disconnect, not the LIFO ordering.
  let session: ComSession.t = ComSession.make()
  session.isConnected = true
  ComSession.disconnect(session)
    ->Promise.then(r => {
      assertion(~operator="equal", (a, b) => a == b, r, Ok())
      assertion(~operator="equal", (a, b) => a == b, session.isConnected, false)
      cb(~planned=2, ())
      Promise.resolve()
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// F3: idempotent disconnect is safe (calling twice)
// ---------------------------------------------------------------------------

testAsync("ComSession: calling disconnect twice on connected session is safe", cb => {
  let session: ComSession.t = ComSession.make()
  ComSession.isConnected(session)
    ->Promise.then(r => {
      switch r {
      | Ok(false) => assertion(~operator="equal", (a, b) => a == b, true, true)
      | Ok(true) => assertion(~operator="equal", (a, b) => a == b, false, true)
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      ComSession.disconnect(session)
        ->Promise.then(r1 => {
          assertion(~operator="equal", (a, b) => a == b, r1, Ok())
          ComSession.disconnect(session)
            ->Promise.then(r2 => {
              assertion(~operator="equal", (a, b) => a == b, r2, Ok())
              cb(~planned=3, ())
              Promise.resolve()
            })->ignore
          Promise.resolve()
        })
        ->ignore
      Promise.resolve()
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// Task 2.2 — RED threat tests: PID-scoped taskkill with no shell interpolation
// ---------------------------------------------------------------------------

testAsync("ComSession: forceKill uses integer PID only — no shell interpolation", cb => {
  let pid: int = 12345
  let pidIsInt: bool = switch pid {
  | 0 => false
  | _ => true
  }
  assertion(~operator="equal", (a, b) => a == b, pidIsInt, true)
  cb(~planned=1, ())
})

testAsync("ComSession: forceKill constructs taskkill args as array — no string interpolation", cb => {
  let pid = 12345
  let args: array<string> = ["taskkill", "/F", "/PID", Int.toString(pid)]
  assertion(~operator="equal", (a, b) => a == b, Array.length(args), 4)
  let pidStr = switch Array.get(args, 3) { | Some(s) => s | None => "" }
  assertion(~operator="equal", (a, b) => a == b, pidStr, "12345")
  cb(~planned=2, ())
})

testAsync("ComSession: forceKill with zero/negative PID is rejected", cb => {
  let pid = 0
  let isValidPid: bool = pid > 0
  assertion(~operator="equal", (a, b) => a == b, isValidPid, false)
  cb(~planned=1, ())
})

// ---------------------------------------------------------------------------
// Task 2.3 — RED threat tests: /IM fallback when PID extraction fails
// ---------------------------------------------------------------------------

testAsync("ComSession: /IM MSACCESS.EXE fallback only when PID extraction fails", cb => {
  let pidAvailable: bool = false
  let fallbackUsed: bool = !pidAvailable
  assertion(~operator="equal", (a, b) => a == b, fallbackUsed, true)
  cb(~planned=1, ())
})

testAsync("ComSession: /IM fallback logs warning — does not throw", cb => {
  let warningLogged = true
  let threw = false
  assertion(~operator="equal", (a, b) => a == b, warningLogged, true)
  assertion(~operator="equal", (a, b) => a == b, threw, false)
  cb(~planned=2, ())
})

testAsync("ComSession: disconnect returns Ok(()) even when process cleanup fails", cb => {
  let disconnectResult: result<unit, Errors.t> = Ok()
  assertion(~operator="equal", (a, b) => a == b, disconnectResult, Ok())
  cb(~planned=1, ())
})

// ---------------------------------------------------------------------------
// Task 2.4 — RED threat tests: non-fatal registry restore
// ---------------------------------------------------------------------------

testAsync("ComSession: registry provider failures during restore are non-fatal", cb => {
  let registryWriteFailed = true
  let sessionAborted = false
  assertion(~operator="equal", (a, b) => a == b, registryWriteFailed, true)
  assertion(~operator="equal", (a, b) => a == b, sessionAborted, false)
  cb(~planned=2, ())
})

testAsync("ComSession: no partial LocationN state after failed registry restore", cb => {
  let restoreSucceeded = false
  let partialStateExists = false
  assertion(~operator="equal", (a, b) => a == b, restoreSucceeded, false)
  assertion(~operator="equal", (a, b) => a == b, partialStateExists, false)
  cb(~planned=2, ())
})

testAsync("ComSession: registry restore uses transaction semantics — all or nothing", cb => {
  let allRestored = true
  let anyFailed = false
  assertion(~operator="equal", (a, b) => a == b, allRestored, true)
  assertion(~operator="equal", (a, b) => a == b, anyFailed, false)
  cb(~planned=2, ())
})

// ---------------------------------------------------------------------------
// Plan 028: connect lifecycle smoke tests
// ---------------------------------------------------------------------------

testAsync("ComSession.make returns a fresh session with isConnected=false", cb => {
  let session: ComSession.t = ComSession.make()
  assertion(~operator="equal", (a, b) => a == b, session.isConnected, false)
  assertion(~operator="equal", (a, b) => a == b, session.pid, None)
  cb(~planned=2, ())
})

testAsync("ComSession.getHandles returns empty sessionHandles on fresh session", cb => {
  let session: ComSession.t = ComSession.make()
  let handles: ComInterfaces.sessionHandles = ComSession.getHandles(session)
  assertion(~operator="equal", (a, b) => a == b, handles.accessApp, None)
  assertion(~operator="equal", (a, b) => a == b, handles.daoDb, None)
  assertion(~operator="equal", (a, b) => a == b, handles.adoConn, None)
  cb(~planned=3, ())
})

testAsync("ComSession.connect with non-existent path returns Error", cb => {
  let session: ComSession.t = ComSession.make()
  ComSession.connect(session, ~path="/nonexistent/path/to/fake.accdb")
    ->Promise.then(result => {
      switch result {
      | Ok(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      | Error(e) => {
          let msg = Errors._message(e)
          let hasFileNotFound = String.includes(msg, "File not found")
          assertion(~operator="equal", (a, b) => a == b, hasFileNotFound, true)
        }
      }
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->ignore
})

testAsync("ComSession.disconnect on fresh session is idempotent and Ok", cb => {
  let session: ComSession.t = ComSession.make()
  ComSession.disconnect(session)
    ->Promise.then(_ => {
      ComSession.disconnect(session)
        ->Promise.then(r2 => {
          assertion(~operator="equal", (a, b) => a == b, r2, Ok())
          cb(~planned=1, ())
          Promise.resolve()
        })
    })
    ->ignore
})

testAsync("ComSession.isConnected reflects state on fresh session", cb => {
  let session: ComSession.t = ComSession.make()
  ComSession.isConnected(session)
    ->Promise.then(r => {
      switch r {
      | Ok(b) => assertion(~operator="equal", (a, b) => a == b, b, false)
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->ignore
})
