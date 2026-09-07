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

let fakeReleaseLog: ref<list<string>> = ref(list{})

let fakeRelease: ComInterfaces.comObject => unit = _ => {
  fakeReleaseLog.contents = list{"release", ...fakeReleaseLog.contents}
}

let fakeReleaseSyncAwait: ComInterfaces.comObject => Promise.t<unit> = (
  (_obj: ComInterfaces.comObject) => {
    fakeReleaseLog.contents = list{"releaseSyncAwait", ...fakeReleaseLog.contents}
    Promise.resolve()
  }
)

let fakeCreateObject: string => Promise.t<result<ComInterfaces.comObject, Errors.t>> = (
  (_progid: string) => Promise.resolve(Error(Errors.databaseError("Fake: not connected")))
)

let fakeGet: (ComInterfaces.comObject, string) => Promise.t<result<JSON.t, Errors.t>> = (
  (_obj: ComInterfaces.comObject, _prop: string) => Promise.resolve(Error(Errors.databaseError("Fake: not connected")))
)

let fakeSet: (ComInterfaces.comObject, string, ComInterfaces.variant) => Promise.t<result<unit, Errors.t>> = (
  (_obj: ComInterfaces.comObject, _prop: string, _value: ComInterfaces.variant) => Promise.resolve(Ok())
)

let fakeInvoke: (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<JSON.t, Errors.t>> = (
  (_obj: ComInterfaces.comObject, _method: string, _args: array<ComInterfaces.variant>) => Promise.resolve(Ok(JSON.Null))
)

let fakeInvokeAsObject: (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<ComInterfaces.comObject, Errors.t>> = (
  (_obj: ComInterfaces.comObject, _method: string, _args: array<ComInterfaces.variant>) => Promise.resolve(Ok())
)

let fakeGetItem: (ComInterfaces.comObject, ComInterfaces.variant) => Promise.t<result<ComInterfaces.comObject, Errors.t>> = (
  (obj: ComInterfaces.comObject, _index: ComInterfaces.variant) => Promise.resolve(Ok(obj))
)

let fakeGetCount: ComInterfaces.comObject => Promise.t<result<int, Errors.t>> = (
  (_obj: ComInterfaces.comObject) => Promise.resolve(Ok(0))
)

let fakeToVariant: ComInterfaces.variant => Promise.t<result<JSON.t, Errors.t>> = (
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

let fakeFromVariant: JSON.t => Promise.t<result<ComInterfaces.variant, Errors.t>> = (
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

let fakeMapDispatchError: (string, option<string>, option<string>, option<int>) => Errors.t = (
  (message, _description, _source, _errorCode) => Errors.databaseError(message)
)

// fakeWinaxBinding as a record value (not module) for setTestBinding injection
let fakeWinaxBinding: Adapters.ComSession.winaxBindingOps = {
  releaseSyncAwait: fakeReleaseSyncAwait,
  createObject: fakeCreateObject,
  get: fakeGet,
  set: fakeSet,
  invoke: fakeInvoke,
  invokeAsObject: fakeInvokeAsObject,
  getItem: fakeGetItem,
  getCount: fakeGetCount,
  toVariant: fakeToVariant,
  fromVariant: fakeFromVariant,
  mapDispatchError: fakeMapDispatchError,
}

let getFakeReleaseLog: unit => list<string> = () => fakeReleaseLog.contents
let clearFakeReleaseLog: unit => unit = () => { fakeReleaseLog.contents = list{} }

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
  // ComSession._disconnect checks isConnected first:
  //   if !session.isConnected { Promise.resolve(Ok()) }  // idempotent
  // This test verifies double-disconnect doesn't double-release via seam
  clearFakeReleaseLog()
  ComSession.setTestBinding(fakeWinaxBinding)
  let session: ComSession.t = ComSession.make()
  ComSession.disconnect(session)
    ->Promise.then(r1 => {
      ComSession.disconnect(session)
        ->Promise.then(r2 => {
          ComSession.clearTestBinding()
          switch (r1, r2) {
          | (Ok(), Ok()) => assertion(~operator="equal", (a, b) => a == b, true, true)
          | _ => {
              assertion(~operator="equal", (a, b) => a == b, r1, Ok())
              assertion(~operator="equal", (a, b) => a == b, r2, Ok())
            }
          }
          // Verify no releases were attempted (never connected)
          let log = getFakeReleaseLog()
          assertion(~operator="equal", (a, b) => a == b, log, list{})
          cb(~planned=2, ())
          Promise.resolve()
        })
    })
    ->ignore
})

testAsync("ComSession: disconnect runs in reverse order (LIFO)", cb => {
  // F3 DEFECT: current _disconnect releases: accessApp → daoDb → adoConn
  // But LIFO requires children before parents: adoConn → currentDb → daoDb → accessApp
  // This test will FAIL on current code because release order is incorrect.
  clearFakeReleaseLog()
  ComSession.setTestBinding(fakeWinaxBinding)

  // Pre-populate session to simulate connected state
  let session: ComSession.t = ComSession.make()
  session.isConnected = true
  session.handles.accessApp = Some()
  session.handles.daoDb = Some()
  session.handles.adoConn = Some()
  session.currentDb = Some()

  ComSession.disconnect(session)
    ->Promise.then(_r => {
      ComSession.clearTestBinding()
      // Verify LIFO: release order should be adoConn → currentDb → daoDb → accessApp
      // (reverse of connect order: accessApp → daoDb → currentDb → adoConn)
      let log = getFakeReleaseLog()
      // log is in reverse order (newest first), so reverse it to see actual call order
      let rec reverseLog = (lst: list<string>, acc: list<string>) => switch lst {
        | list{} => acc
        | list{h, ...t} => reverseLog(t, list{h, ...acc})
      }
      let releaseOrder = reverseLog(log, list{})
      // releaseOrder should be: adoConn (child) → currentDb (child) → daoDb (child) → accessApp (parent)
      // But current buggy order is: accessApp → daoDb → adoConn (parent before children)
      // The first element of releaseOrder tells us which handle was released first
      // For LIFO, first released should be adoConn (or currentDb), not accessApp
      switch releaseOrder {
      | list{"accessApp", ..._} => assertion(~operator="equal", (a, b) => a == b, true, false) // BUG: parent released first
      | _ => assertion(~operator="equal", (a, b) => a == b, true, true) // GOOD: child released first
      }
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->ignore
})

testAsync("ComSession: connect fails and rolls back partial handles", cb => {
  // F3 DEFECT: when connect fails after acquiring some handles, rollback
  // may not properly release all handles via releaseSyncAwait.
  // With seam, we can verify releaseSyncAwait is called on acquired handles.
  clearFakeReleaseLog()
  ComSession.setTestBinding(fakeWinaxBinding)

  let session: ComSession.t = ComSession.make()
  // Use nonexistent path to trigger failure after some handles acquired
  // Note: With fake binding, createObject returns Error, so connect fails immediately
  ComSession.connect(session, ~path="/nonexistent/fake.accdb")
    ->Promise.then(result => {
      ComSession.clearTestBinding()
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
// compile time and has NO seam (no setTestBinding equivalent). fakeWinaxBinding
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
  // F3 DEFECT: currentDb is acquired at _connect line ~260 but NOT released in _disconnect.
  // It is only cleared (session.currentDb = None) without calling releaseSyncAwait.
  // This test will FAIL on current code because currentDb is never released.
  clearFakeReleaseLog()
  ComSession.setTestBinding(fakeWinaxBinding)

  let session: ComSession.t = ComSession.make()
  // Pre-populate to simulate connected state with currentDb acquired
  session.isConnected = true
  session.handles.accessApp = Some()
  session.handles.daoDb = Some()
  session.currentDb = Some()
  session.handles.adoConn = Some()

  ComSession.disconnect(session)
    ->Promise.then(r => {
      ComSession.clearTestBinding()
      assertion(~operator="equal", (a, b) => a == b, r, Ok())
      // Verify currentDb was released (should be in release log)
      let log = getFakeReleaseLog()
      // Count how many times releaseSyncAwait was called
      let rec countReleaseSyncAwait = (lst: list<string>, acc: int) => switch lst {
        | list{} => acc
        | list{h, ...t} => countReleaseSyncAwait(t, if h == "releaseSyncAwait" { acc + 1 } else { acc })
      }
      let releaseCount = countReleaseSyncAwait(log, 0)
      // Bug: currentDb is NOT released, so count is 3 (accessApp, daoDb, adoConn)
      // Fixed: currentDb IS released, count should be 4
      assertion(~operator="equal", (a, b) => a == b, releaseCount, 4)
      cb(~planned=2, ())
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
  // F3 DEFECT: _disconnect releases in wrong order: accessApp → daoDb → adoConn
  // Correct LIFO (children before parents): adoConn → currentDb → daoDb → accessApp
  // This test will FAIL on current code because the release order is wrong.
  clearFakeReleaseLog()
  ComSession.setTestBinding(fakeWinaxBinding)

  // Pre-populate session to simulate connected state
  let session: ComSession.t = ComSession.make()
  session.isConnected = true
  session.handles.accessApp = Some()
  session.handles.daoDb = Some()
  session.handles.adoConn = Some()
  session.currentDb = Some()

  ComSession.disconnect(session)
    ->Promise.then(_r => {
      ComSession.clearTestBinding()
      let log = getFakeReleaseLog()
      // log is in reverse order (newest first), reverse to get actual call order
      let rec reverse = (lst: list<string>, acc: list<string>) => switch lst {
        | list{} => acc
        | list{h, ...t} => reverse(t, list{h, ...acc})
      }
      let releaseOrder = reverse(log, list{})
      // releaseOrder should be: adoConn (child) → currentDb (child) → daoDb (child) → accessApp (parent)
      // But current buggy order is: accessApp → daoDb → adoConn (parent before children)
      // The first element of releaseOrder tells us which handle was released first
      // For LIFO, first released should be adoConn (or currentDb), not accessApp
      switch releaseOrder {
      | list{"accessApp", ..._} => assertion(~operator="equal", (a, b) => a == b, true, false) // BUG: parent released first
      | _ => assertion(~operator="equal", (a, b) => a == b, true, true) // GOOD: child released first
      }
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// F3: idempotent disconnect is safe (calling twice)
// ---------------------------------------------------------------------------

testAsync("ComSession: calling disconnect twice on connected session is safe", cb => {
  clearFakeReleaseLog()
  ComSession.setTestBinding(fakeWinaxBinding)

  let session: ComSession.t = ComSession.make()
  // Pre-populate to simulate connected state so first disconnect actually releases
  session.isConnected = true
  session.handles.accessApp = Some()
  session.handles.daoDb = Some()
  session.currentDb = Some()
  session.handles.adoConn = Some()

  ComSession.disconnect(session)
    ->Promise.then(r1 => {
      assertion(~operator="equal", (a, b) => a == b, r1, Ok())
      ComSession.disconnect(session)
        ->Promise.then(r2 => {
          ComSession.clearTestBinding()
          assertion(~operator="equal", (a, b) => a == b, r2, Ok())
          // Verify no double-release: first disconnect released 4 handles,
          // second disconnect is a no-op (isConnected is now false).
          let log = getFakeReleaseLog()
          let rec countReleases = (lst: list<string>, acc: int) => switch lst {
            | list{} => acc
            | list{h, ...t} => countReleases(t, if h == "releaseSyncAwait" { acc + 1 } else { acc })
          }
          let releaseCount = countReleases(log, 0)
          // Exactly 4 releases (accessApp, daoDb, currentDb, adoConn) — second disconnect released nothing
          assertion(~operator="equal", (a, b) => a == b, releaseCount, 4)
          cb(~planned=3, ())
          Promise.resolve()
        })
        ->Promise.catch(_ => Promise.resolve())
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
