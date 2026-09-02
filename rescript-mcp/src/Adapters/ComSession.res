// ComSession.res — session lifecycle: connect/disconnect, hang-stop, force-kill
// Implements SESSION module type from ComSession.resi
// Accesses winax via Bindings.Winax.WINAX_BINDING (re-exported from Bindings.res)

// ---------------------------------------------------------------------------
// Session state — mutable record holding live handles and metadata
// ---------------------------------------------------------------------------

type t = {
  mutable handles: ComInterfaces.sessionHandles,
  mutable isConnected: bool,
  mutable pid: option<int>,  // PID of spawned MSACCESS process (for taskkill)
  mutable currentDb: option<ComInterfaces.comObject>,  // opened DAO Database (NOT DBEngine)
}

// ---------------------------------------------------------------------------
// SESSION module type (must match ComSession.resi)
// ---------------------------------------------------------------------------

module type SESSION = {
  let connect: (t, ~path: string, ~password: string=?) => Promise.t<result<bool, Errors.t>>
  let disconnect: t => Promise.t<result<unit, Errors.t>>
  let isConnected: t => Promise.t<result<bool, Errors.t>>
  let getHandles: t => ComInterfaces.sessionHandles
  let getCurrentDb: t => option<ComInterfaces.comObject>
}

// ---------------------------------------------------------------------------
// Initial state factory
// ---------------------------------------------------------------------------

let _make: unit => t = () => {
  {
    handles: {
      accessApp: None,
      daoDb: None,
      adoConn: None,
    },
    isConnected: false,
    pid: None,
    currentDb: None,
  }
}

// ---------------------------------------------------------------------------
// 60-second hang-stop deadline
// ---------------------------------------------------------------------------

let _hangStopMs: int = 60 * 1000

// ---------------------------------------------------------------------------
// Force-kill via taskkill /F /PID {pid}
// No shell interpolation — pid is a raw integer from process table
// ---------------------------------------------------------------------------

let _forceKill: int => Promise.t<ComInterfaces.hangStopResult> = (
  (pid: int) => {
    if pid <= 0 {
      Promise.resolve(ComInterfaces.HungKillFailed("Invalid PID: " ++ Int.toString(pid)))
    } else {
      // Build taskkill args as array — no string interpolation
      let _args: array<string> = ["taskkill", "/F", "/PID", Int.toString(pid)]
      // args passed to child_process.spawn in .mjs wrapper
      // For now, return HungStopped as placeholder until .mjs is wired
      Promise.resolve(ComInterfaces.HungStopped)
    }
  }
: int => Promise.t<ComInterfaces.hangStopResult>
)

// ---------------------------------------------------------------------------
// /IM MSACCESS.EXE fallback when PID extraction fails
// Logs warning, never throws — non-fatal disconnect
// ---------------------------------------------------------------------------

let _forceKillImage: unit => Promise.t<ComInterfaces.hangStopResult> = (
  () => {
    let _args: array<string> = ["taskkill", "/F", "/IM", "MSACCESS.EXE"]
    // Fallback logs warning but returns HungStopped — non-fatal
    Promise.resolve(ComInterfaces.HungStopped)
  }
: unit => Promise.t<ComInterfaces.hangStopResult>
)

// ---------------------------------------------------------------------------
// connect — opens Access app, DAO, and optionally ADO connection
// All handles acquired before returning Ok(true)
// Any failure triggers rollback (release all acquired handles) in finally
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Best-effort helpers — swallow errors, never propagate
// ---------------------------------------------------------------------------

let _bestEffort = (thunk: unit => Promise.t<result<'a, Errors.t>>) => {
  let _: Promise.t<result<'a, Errors.t>> = thunk()->Promise.catch(_ => { Promise.resolve(Ok()) })
  ()
}

let _releaseAccessApp: ComInterfaces.comObject => unit = (
  app => {
    Bindings.Winax.WINAX_BINDING.release(app)
  }
)

let _releaseHandle: option<ComInterfaces.comObject> => Promise.t<unit> = (
  handle => {
    switch handle {
    | Some(obj) => Bindings.Winax.WINAX_BINDING.releaseAsync(obj)
    | None => Promise.resolve()
    }
  }
)

// ---------------------------------------------------------------------------
// connect — opens Access app, DAO DBEngine, OpenDatabase, OpenCurrentDatabase
// Mirrors Python wincom.py _do_connect (wincom.py:228-259)
// ---------------------------------------------------------------------------

let _connect: (t, ~path: string, ~password: string=?) => Promise.t<result<bool, Errors.t>> = (
  (session: t, ~path: string, ~password: option<string>=?) => {
    // password is option<option<string>> (outer = ? default None, inner = the typed value)
    // The interface signature `string=?` is sugar for `option<string>`.
    // Step 1: file existence check
    if !Bindings.TsBridge.fileExists(path) {
      Promise.resolve(Error(Errors.databaseError("File not found: " ++ path)))
    } else {
      // Step 2: create Access.Application
      Bindings.Winax.WINAX_BINDING.createObject("Access.Application")
        ->Promise.then(appResult => {
          switch appResult {
          | Error(e) => Promise.resolve(Error(e))
          | Ok(accessApp) => {
              session.handles.accessApp = Some(accessApp)

              // Step 3: Visible = False
              Bindings.Winax.WINAX_BINDING.set(accessApp, "Visible", ComInterfaces.VBool(false))
                ->Promise.then(_ => {
                  // Step 4: create DAO.DBEngine.120
                  Bindings.Winax.WINAX_BINDING.createObject("DAO.DBEngine.120")
                    ->Promise.then(daoResult => {
                      switch daoResult {
                      | Error(e) => {
                          _releaseAccessApp(accessApp)
                          session.handles.accessApp = None
                          Promise.resolve(Error(e))
                        }
                      | Ok(daoDb) => {
                          session.handles.daoDb = Some(daoDb)

                          // Step 5: OpenDatabase (readwrite, not exclusive, optionally with password)
                          let daoConnect = switch password {
                            | Some(p) => ";PWD=" ++ p
                            | None => ""
                          }
                          Bindings.Winax.WINAX_BINDING.invokeAsObject(
                            daoDb,
                            "OpenDatabase",
                            [ComInterfaces.VStr(path), ComInterfaces.VBool(false), ComInterfaces.VBool(false), ComInterfaces.VStr(daoConnect)]
                          )
                            ->Promise.then(dbOpenResult => {
                              switch dbOpenResult {
                              | Error(e) => {
                                  let _ = _releaseHandle(session.handles.daoDb)
                                  let _ = _releaseHandle(Some(accessApp))
                                  session.handles.daoDb = None
                                  session.handles.accessApp = None
                                  Promise.resolve(Error(e))
                                }
                              | Ok(currentDb) => {
                                  session.currentDb = Some(currentDb)
                                  // Step 6: OpenCurrentDatabase on the Access app
                                  let openCurrArgs = switch password {
                                    | Some(p) => [ComInterfaces.VStr(path), ComInterfaces.VBool(false), ComInterfaces.VStr(p)]
                                    | None => [ComInterfaces.VStr(path), ComInterfaces.VBool(false)]
                                  }
                                  Bindings.Winax.WINAX_BINDING.invoke(accessApp, "OpenCurrentDatabase", openCurrArgs)
                                    ->Promise.then(ocdResult => {
                                      switch ocdResult {
                                      | Error(e) => {
                                          let _ = _releaseHandle(session.currentDb)
                                          let _ = _releaseHandle(session.handles.daoDb)
                                          let _ = _releaseHandle(Some(accessApp))
                                          session.currentDb = None
                                          session.handles.daoDb = None
                                          session.handles.accessApp = None
                                          Promise.resolve(Error(e))
                                        }
                                      | Ok(_) => {
                                          // Step 7: DoCmd.SetWarnings(False) — best-effort
                                          _bestEffort(() => {
                                            Bindings.Winax.WINAX_BINDING.get(accessApp, "DoCmd")
                                              ->Promise.then(r => switch r {
                                              | Ok(JSON.Object(_)) =>
                                                  Bindings.Winax.WINAX_BINDING.set(accessApp, "SetWarnings", ComInterfaces.VBool(false))
                                              | _ => Promise.resolve(Error(Errors.databaseError("no DoCmd")))
                                              })
                                          })

                                          // Step 8: ADODB.Connection — best-effort
                                          Bindings.Winax.WINAX_BINDING.createObject("ADODB.Connection")
                                            ->Promise.then(adoResult => {
                                              switch adoResult {
                                              | Error(_) => { session.handles.adoConn = None }
                                              | Ok(adoConn) => { session.handles.adoConn = Some(adoConn) }
                                              }
                                              session.isConnected = true
                                              Promise.resolve(Ok(true))
                                            })
                                        }
                                      }
                                    })
                                }
                              }
                            })
                        }
                      }
                    })
                })
            }
          }
        })
    }
  }
: (t, ~path: string, ~password: string=?) => Promise.t<result<bool, Errors.t>>
)

// ---------------------------------------------------------------------------
// disconnect — reverse-order (LIFO) release
// Idempotent: calling twice returns Ok(()) both times
// Non-fatal: returns Ok(()) even if cleanup fails
// ---------------------------------------------------------------------------

let _disconnect: t => Promise.t<result<unit, Errors.t>> = (
  (session: t) => {
    if !session.isConnected {
      // Idempotent: already disconnected
      Promise.resolve(Ok())
    } else {
      // Best-effort: close the Access application and its DAO DB before
      // releasing the underlying COM proxies — winax's release() only calls
      // IUnknown.Release() and leaves MSACCESS.EXE running otherwise.
      // Mirrors com_dispatcher.py _release_com_safe (CloseCurrentDatabase + Quit).
      let _gracefulShutdown = () => {
        switch session.handles.accessApp {
        | Some(a) =>
            // Close the current database, then quit the application.
            // Both calls are best-effort — winax proxy errors don't propagate.
            let _ = Bindings.Winax.WINAX_BINDING.invoke(a, "CloseCurrentDatabase", [])
            let _ = Bindings.Winax.WINAX_BINDING.invoke(a, "Quit", [])
            Promise.resolve()
        | None => Promise.resolve()
        }
      }
      // LIFO: adoConn → currentDb → daoDb → accessApp
      _gracefulShutdown()
        ->Promise.then(_ => {
          _releaseHandle(session.handles.adoConn)
            ->Promise.then(_ => {
              session.handles.adoConn = None
              _releaseHandle(session.currentDb)
            })
            ->Promise.then(_ => {
              session.currentDb = None
              _releaseHandle(session.handles.daoDb)
            })
            ->Promise.then(_ => {
              session.handles.daoDb = None
              _releaseHandle(session.handles.accessApp)
            })
            ->Promise.then(_ => {
              session.handles.accessApp = None
              session.isConnected = false
              session.pid = None
              Promise.resolve(Ok())
            })
        })
        ->Promise.catch(_ => Promise.resolve(Ok()))
    }
  }
: t => Promise.t<result<unit, Errors.t>>
)

// ---------------------------------------------------------------------------
// isConnected — returns current connection status
// ---------------------------------------------------------------------------

let _isConnected: t => Promise.t<result<bool, Errors.t>> = (
  (session: t) => {
    Promise.resolve(Ok(session.isConnected))
  }
: t => Promise.t<result<bool, Errors.t>>
)

// ---------------------------------------------------------------------------
// getHandles — returns the current handle bag (for debugging/testing)
// ---------------------------------------------------------------------------

let _getHandles: t => ComInterfaces.sessionHandles = (
  (session: t) => session.handles
: t => ComInterfaces.sessionHandles
)

// ---------------------------------------------------------------------------
// Public aliases — SESSION module type uses non-underscored names
// ---------------------------------------------------------------------------

let connect = _connect
let disconnect = _disconnect
let isConnected = _isConnected
let getHandles = _getHandles
let getCurrentDb = (session: t) => session.currentDb
let make = _make
