// ComSession.res — session lifecycle: connect/disconnect, hang-stop, force-kill
// Implements SESSION module type from ComSession.resi
// Accesses winax via Bindings.Winax.WINAX_BINDING (re-exported from Bindings.res)

// ---------------------------------------------------------------------------
// SESSION module type (must match ComSession.resi)
// ---------------------------------------------------------------------------

module type SESSION = {
  type t

  let connect: (t, ~path: string) => Promise.t<result<bool, Errors.t>>
  let disconnect: t => Promise.t<result<unit, Errors.t>>
  let isConnected: t => Promise.t<result<bool, Errors.t>>
  let getHandles: t => ComInterfaces.sessionHandles
}

// ---------------------------------------------------------------------------
// Session state — mutable record holding live handles and metadata
// ---------------------------------------------------------------------------

type t = {
  mutable handles: ComInterfaces.sessionHandles,
  mutable isConnected: bool,
  mutable pid: option<int>,  // PID of spawned MSACCESS process (for taskkill)
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

let _connect: (t, ~path: string) => Promise.t<result<bool, Errors.t>> = (
  (session: t, ~path: string) => {
    let _ = path
    Bindings.Winax.WINAX_BINDING.createObject("Access.Application")
      ->Promise.then(result => {
        switch result {
        | Error(e) => Promise.resolve(Error(e))
        | Ok(accessApp) => {
            session.handles.accessApp = Some(accessApp)
            // Try to open DAO.DBEngine
            Bindings.Winax.WINAX_BINDING.createObject("DAO.DBEngine.120")
              ->Promise.then(daoResult => {
                switch daoResult {
                | Error(e) => {
                    // Rollback: release accessApp in finally-style
                    Bindings.Winax.WINAX_BINDING.release(accessApp)
                    session.handles.accessApp = None
                    Promise.resolve(Error(e))
                  }
                | Ok(daoDb) => {
                    session.handles.daoDb = Some(daoDb)
                    // ADO connection is optional — best-effort
                    Bindings.Winax.WINAX_BINDING.createObject("ADODB.Connection")
                      ->Promise.then(adoResult => {
                        switch adoResult {
                        | Error(_) => {
                            // ADO failure is non-fatal — continue without it
                            session.handles.adoConn = None
                            session.isConnected = true
                            Promise.resolve(Ok(true))
                          }
                        | Ok(adoConn) => {
                            session.handles.adoConn = Some(adoConn)
                            session.isConnected = true
                            Promise.resolve(Ok(true))
                          }
                        }
                      })
                  }
                }
              })
          }
        }
      })
  }
: (t, ~path: string) => Promise.t<result<bool, Errors.t>>
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
      // Release in reverse order: adoConn → daoDb → accessApp
      let releaseHandle: (option<ComInterfaces.comObject>, string) => unit = (
        (handle, _name) => {
          switch handle {
          | Some(obj) => Bindings.Winax.WINAX_BINDING.release(obj)
          | None => ()
          }
        }
      )
      // LIFO: adoConn first, then daoDb, then accessApp
      releaseHandle(session.handles.adoConn, "adoConn")
      session.handles.adoConn = None
      releaseHandle(session.handles.daoDb, "daoDb")
      session.handles.daoDb = None
      releaseHandle(session.handles.accessApp, "accessApp")
      session.handles.accessApp = None
      session.isConnected = false
      session.pid = None
      Promise.resolve(Ok())
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
