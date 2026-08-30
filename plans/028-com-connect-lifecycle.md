# Plan 028 — Complete the COM connect lifecycle and winax binding primitives

## Drift check

```bash
git rev-parse --short HEAD        # expected: 0391275 (plan 027 tip)
git status --short                # expected: no tracked-file modifications (untracked junk at root is OK)
git diff --stat 0391275..HEAD -- rescript-mcp/   # expected: empty
```

## Note on test paths (correction from initial draft)

Tests live at `rescript-mcp/test/*.res` (NOT `tests/`). The relevant existing files:

- `rescript-mcp/test/WinaxTest.res` — EXISTS (216 lines). Tests variant types, dispatchError, sessionHandles, hangStopResult, trustedLocation. Does NOT test binding primitives — so a new `test/WinaxBindingTest.res` is needed for the binding primitives work.
- `rescript-mcp/test/ComSessionTest.res` — EXISTS (268 lines) with mostly smoke tests. `FakeWinaxBinding` is defined inside but never injected into the real ComSession. Extend it with real tests.
- `rescript-mcp/test/ComDataAdapterTest.res` — EXISTS (334 lines) with 14 smoke tests. `FakeWinaxBinding` + `FakeComDispatch` defined but never injected. Extend it.

**Fake injection mechanism**: neither file has a working injection seam. `ComDataAdapterTest.res:94-98` defines `_testMode: ref<bool>` but `ComDataAdapter.res` does not check it. Recommend adding an optional `~winax: option<WINAX_BINDING>=?` parameter to `ComSession.connect`/`ComDataAdapter.connect` so tests can inject fakes — small, idiomatic, and keeps the production path unchanged.

## Status

- Status: TODO
- Branch: `rescript/028-com-connect-lifecycle` from `0391275` (the 027 branch tip — its files are the substrate; if 027 merges to main before this plan starts, branch from main)
- Owner: @medium sub-agent
- Effort: M
- Closes: findings C-01, C-09, C-10 (the foundation)

## Environment quirks (MANDATORY — apply to every verification command)

- All commands run in PowerShell. If `pnpm` output is silently lost, wrap in `cmd /c "..."` and redirect to a log file.
- `pnpm install --ignore-scripts` if winax/node-gyp/Python fail. Try plain `pnpm install` first.
- `rescript-mcp/.venv/Scripts/python.exe` for parity — never bare `python`, never `uv`.
- Junk files at repo root (`led.out`, `nul`, `build_output.txt`, `test_output.txt`, `test_output2.txt`) are untracked. Do not commit. Do not `git add -A`.
- `ACCESS_TEST_ASSUME_ACE=1` required to run parity on this machine.
- Conventional commits, no AI attribution, no push, no PR.
- Fresh-build gate: every "suite green" claim must come from `pnpm -C rescript-mcp clean && pnpm -C rescript-mcp build && pnpm -C rescript-mcp test` in one run.
- `pnpm -C rescript-mcp clean` does NOT clear `rescript-mcp/test/*.mjs` (per standard #6); if test compilation is stale, manually delete those.

## Why this matters

Plan 027 wired the COM data adapter end-to-end, but `connect()` only creates an Access.Application handle and marks connected. It never opens the database, never sets `Visible=False`, never dismisses dialogs. The comment at `ComDataAdapter.res:156-158` admits this gap:

```rescript
// Note: Full DAO database opening requires COM collection iteration
// which the winax stubs don't support. We mark connected
// based on having the Access app handle.
```

Every COM tool downstream (executeQuery, getTables, mutations, DDL — plans 029-032) is unreachable against any real `.accdb` until connect actually opens a DB.

Four winax binding primitives are no-op stubs (`set`, `getItem`, `getCount`, `release`). Property writes silently fail. `OpenDatabase` returns a live COM handle that the current FFI cannot store. COM objects leak on disconnect.

`ComSession._connect` has the same gap — it creates `Access.Application`, `DAO.DBEngine.120`, and `ADODB.Connection` objects but never opens a database, and `let _ = path` ignores the file argument.

This plan closes the foundation. Plans 029 (executeQuery), 030 (schema reads), 031 (mutations), 032 (DDL) all build on a working connect + a complete binding surface.

## Current state (verified)

### `src/Adapters/ComDataAdapter.res:117-198` — `DaoAdapter` module

```rescript
module DaoAdapter = {
  type t = comDataAdapterState    // mutable: isConnected, dbPath, accessApp, daoDb, dispatcher

  let make: unit => t = () => _make()

  let connect = (self: t, dbPath: string, ~password: option<string>=?): Promise.t<result<bool, Errors.t>> => {
    if !_isWindows() {
      Promise.resolve(_platformError("COM automation requires Windows"))
    } else {
      let dispatcher = ComDispatch.make()
      self.dispatcher = Some(dispatcher)
      ComDispatch.enqueue(dispatcher, () => {
        Bindings.Winax.WINAX_BINDING.createObject("Access.Application")
          ->Promise.then(appResult => {
            switch appResult {
            | Error(e) => Promise.resolve(Error(e))
            | Ok(accessApp) => {
                self.accessApp = Some(accessApp)
                _setProperty(~obj=accessApp, ~property="Visible", ~value=ComInterfaces.VBool(false))
                  ->Promise.then(_ => {
                    _getProperty(~obj=accessApp, ~property="DBEngine")
                      ->Promise.then(dbEngineResult => {
                        switch dbEngineResult {
                        | Error(e) => Promise.resolve(Error(e))
                        | Ok(_) => {
                            self.isConnected = true
                            self.dbPath = Some(dbPath)
                            Promise.resolve(Ok(true))    // <-- lies: DAO DB never opened
                          }
                        }
                      })
                  })
              }
            }
          })
          ->Promise.catch(e => Promise.resolve(Error(Errors.databaseError(_exnMessage(e)))))
      })
    }
  }

  let disconnect = (self: t): Promise.t<result<unit, Errors.t>> => {
    if !self.isConnected { Promise.resolve(Ok()) }
    else {
      switch self.accessApp {
      | Some(app) => { Bindings.Winax.WINAX_BINDING.release(app)->ignore; self.accessApp = None }
      | None => ()
      }
      self.daoDb = None
      self.isConnected = false
      self.dbPath = None
      self.dispatcher = None
      Promise.resolve(Ok())
    }
  }
}
```

### `src/Adapters/ComSession.res:90-135` — also stubbed (with comment)

```rescript
let _connect: (t, ~path: string) => Promise.t<result<bool, Errors.t>> = (
  (session: t, ~path: string) => {
    let _ = path    // <-- path ignored!
    Bindings.Winax.WINAX_BINDING.createObject("Access.Application")
      ->Promise.then(result => {
        switch result {
        | Error(e) => Promise.resolve(Error(e))
        | Ok(accessApp) => {
            session.handles.accessApp = Some(accessApp)
            Bindings.Winax.WINAX_BINDING.createObject("DAO.DBEngine.120")
              ->Promise.then(daoResult => {
                switch daoResult {
                | Error(e) => {
                    Bindings.Winax.WINAX_BINDING.release(accessApp)
                    session.handles.accessApp = None
                    Promise.resolve(Error(e))
                  }
                | Ok(daoDb) => {
                    session.handles.daoDb = Some(daoDb)
                    Bindings.Winax.WINAX_BINDING.createObject("ADODB.Connection")
                      ->Promise.then(adoResult => {
                        switch adoResult {
                        | Error(_) => { session.handles.adoConn = None; session.isConnected = true; Promise.resolve(Ok(true)) }
                        | Ok(adoConn) => { session.handles.adoConn = Some(adoConn); session.isConnected = true; Promise.resolve(Ok(true)) }
                        }
                      })
                  }
                }
              })
          }
        }
      })
  }
)
```

### `src/Bindings/Winax.res:9-31` — module type

```rescript
module type WINAX_BINDING = {
  let createObject: string => Promise.t<result<ComInterfaces.comObject, Errors.t>>
  let release: ComInterfaces.comObject => unit
  let get: (ComInterfaces.comObject, string) => Promise.t<result<JSON.t, Errors.t>>
  let set: (ComInterfaces.comObject, string, ComInterfaces.variant) => Promise.t<result<unit, Errors.t>>
  let invoke: (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<JSON.t, Errors.t>>
  let getItem: (ComInterfaces.comObject, ComInterfaces.variant) => Promise.t<result<ComInterfaces.comObject, Errors.t>>
  let getCount: ComInterfaces.comObject => Promise.t<result<int, Errors.t>>
  let toVariant: ComInterfaces.variant => Promise.t<result<JSON.t, Errors.t>>
  let fromVariant: JSON.t => Promise.t<result<ComInterfaces.variant, Errors.t>>
  let mapDispatchError: (string, option<string>, option<string>, option<int>) => Errors.t
}
```

### `src/Bindings/Winax.res:154-159` — `set` stub

```rescript
let set: (ComInterfaces.comObject, string, ComInterfaces.variant) => Promise.t<result<unit, Errors.t>> = (
  (_obj: ComInterfaces.comObject, _property: string, _value: ComInterfaces.variant) => {
    Promise.resolve(Ok())    // <-- no-op
  }
)
```

### `src/Bindings/Winax.res:123-128, 187-203` — `release`, `getItem`, `getCount` stubs

```rescript
let release: ComInterfaces.comObject => unit = (
  (_obj: ComInterfaces.comObject) => { () } // placeholder
)

let getItem: (ComInterfaces.comObject, ComInterfaces.variant) => Promise.t<result<ComInterfaces.comObject, Errors.t>> = (
  (obj, _index) => { Promise.resolve(Ok(obj)) }  // returns input unchanged
)

let getCount: ComInterfaces.comObject => Promise.t<result<int, Errors.t>> = (
  (_obj) => { Promise.resolve(Ok(0)) }  // always 0
)
```

### `src/Js/winaxBinding.mts:1-39` — TypeScript bridge (gaps)

```typescript
export interface WinaxModule {
  Object: (progid: string) => unknown
  cast: (obj: unknown, prop: string) => unknown    // used for get
  invoke: (obj: unknown, method: string, args: unknown[]) => unknown
  // MISSING: release() or any setter hook
}

export const createObject   = (mod, progid) => mod.Object(progid)
export const getProperty    = (mod, obj, prop) => mod.cast(obj, prop)
export const invokeMethod   = (mod, obj, method, args) => mod.invoke(obj, method, args)
// MISSING: setProperty, release, invokeReturningObject, getCount helper
```

### `src/ms_access_mcp/adapters/wincom.py:178-232` — Python oracle (verified)

```python
if not os.path.exists(db_path):
    return False
self._ensure_windows()
self._dispatcher.start()
self._db_path = db_path
self._dispatcher.set_db_path(db_path)

def _do_connect() -> bool:
    import win32com.client
    try:
        self._dispatcher._access_app = win32com.client.Dispatch("Access.Application")
        self._dispatcher._access_app.Visible = False

        dao_connect = f";PWD={password}" if password else ""
        dbe = self._dispatcher._access_app.DBEngine
        self._dispatcher._current_db = dbe.OpenDatabase(
            db_path, False, False, dao_connect
        )
        self._dispatcher._access_app.OpenCurrentDatabase(db_path, False, password)

        try:
            self._dispatcher._access_app.DoCmd.SetWarnings(False)
        except Exception:
            pass

        self._dispatcher._ado_conn = (
            self._dispatcher._access_app.CurrentProject.Connection
        )

        import time; time.sleep(0.5)
        self._dispatcher._dismiss_access_dialogs()

        return True
    except Exception as _ex:
        self._dispatcher._release_com_safe()
        _logger.exception(f"[WinComAdapter] _do_connect FAILED: {_ex}")
        return False

return self._dispatcher.call(_do_connect)
```

The Python oracle opens DAO FIRST (readwrite), then OpenCurrentDatabase. DoCmd.SetWarnings(False) is best-effort (catches). CurrentProject.Connection is best-effort. A 0.5s sleep then dialog dismissal. **Mirror this sequence exactly.**

### Existing tests

- `rescript-mcp/test/ComDataAdapterTest.res` — 14 tests, mostly smoke-tests of result shapes; `FakeWinaxBinding` defined but never injected
- `rescript-mcp/test/ComSessionTest.res` — exists, mostly smoke-tests of expected types; `FakeWinaxBinding` defined but never injected
- `rescript-mcp/test/WinaxTest.res` — EXISTS but tests variant types, not binding primitives; create a new `test/WinaxBindingTest.res` for the primitives

Read these files before extending. Match the existing fake pattern (likely a record of recorded calls; check `_recordingFake` or similar).

## Commands

| Goal | Command |
|------|---------|
| Build | `pnpm -C rescript-mcp clean && pnpm -C rescript-mcp build` |
| Test | `pnpm -C rescript-mcp test` |
| Parity (subset) | `cd rescript-mcp && ACCESS_TEST_ASSUME_ACE=1 .venv/Scripts/python.exe -m pytest ../parity -m "not com_integration"` |
| Drift | `git diff --stat 0391275..HEAD -- rescript-mcp/` (must be empty after commit) |
| Type check | `pnpm -C rescript-mcp check-types` (or whatever the project uses — verify by reading `package.json` scripts) |

## Scope

IN scope:
- `src/Js/winaxBinding.mts` — add `setProperty`, `release`, `invokeReturningObject` (winax API verified at `node_modules/.pnpm/winax@3.6.9/node_modules/winax/index.d.ts`; `release` is a free function, property writes via direct assignment, `invoke` returns COM proxy as `unknown`)
- `src/TsBridge.res` — add externs for the new .mts functions; add `winaxInvokeReturningObject` returning `comObject` not `JSON.t`
- `src/Bindings/Winax.res` + `Winax.resi` — wire `set`, `release`, `getCount`, `getItem`, new `invokeAsObject` to real implementations
- `src/Adapters/ComSession.res` — make `_connect` actually open the DB (mirror Python `wincom.py:178-232`); add rollback helper; add optional `~winax: option<WINAX_BINDING>=?` parameter for fake injection in tests
- `src/Adapters/ComDataAdapter.res` — make `DaoAdapter.connect`/`disconnect` delegate to `ComSession` (drop duplicate lifecycle); drop `dispatcher`/`accessApp`/`daoDb` fields; add `mutable session: option<ComSession.t>`; pass the optional `~winax` through
- Tests: extend `test/ComSessionTest.res` and `test/ComDataAdapterTest.res`, create new `test/WinaxBindingTest.res`. Match existing fake pattern. The `~winax` injection seam must be used.
- Update `plans/README.md` row 028 → DONE with the final SHA after completion

OUT of scope (other plans):
- Plan 029 — executeQuery via DAO OpenRecordset
- Plan 030 — schema reads (getTables, getRelationships, etc.)
- Plan 031 — mutations (insertData, updateData, deleteData, executeRawSql)
- Plan 032 — DDL surface

## Git workflow

1. `git checkout -b rescript/028-com-connect-lifecycle 0391275`
2. Suggested commit order (one logical step each):
   - `feat(rescript-mcp): complete winax binding primitives` (winaxBinding.mts + Winax.res + TsBridge externs)
   - `feat(rescript-mcp): open DAO database in ComSession.connect`
   - `refactor(rescript-mcp): ComDataAdapter delegates lifecycle to ComSession`
   - `test(rescript-mcp): cover connect lifecycle and binding primitives`
3. Verify all commands green.
4. Update `plans/README.md` row 028 with the final SHA and DONE.
5. Stamp this plan file with the final SHA at the bottom.

## Steps

### Step 1 — Extend the winax bridge

Add to `src/Js/winaxBinding.mts`:

```typescript
export interface WinaxModule {
  Object:   (progid: string) => unknown
  cast:     (obj: unknown, prop: string) => unknown
  invoke:   (obj: unknown, method: string, args: unknown[]) => unknown
  release:  (obj: unknown) => void           // verify winax exposes this — read node_modules/winax index.d.ts
  // winax property writes happen via direct JS assignment: `obj.prop = value`.
  // We expose a typed setter that does `obj[prop] = value` after unwrapping any IDispatch wrapper.
}

export const setProperty = (
  mod: WinaxModule,
  obj: unknown,
  prop: string,
  value: unknown,
): void => {
  // winax COM proxies support direct property assignment on the JS wrapper.
  // The exact mechanism depends on winax version — verify in node_modules/winax.
  (obj as Record<string, unknown>)[prop] = value
}

export const release = (
  mod: WinaxModule,
  obj: unknown,
): void => {
  if (typeof mod.release === "function") {
    mod.release(obj)
  }
  // Fallback: no-op if winax has no release
}

export const invokeReturningObject = (
  mod: WinaxModule,
  obj: unknown,
  method: string,
  args: unknown[],
): unknown => mod.invoke(obj, method, args)
```

**The sub-agent must verify the winax API** (read `node_modules/.pnpm/winax@3.6.9/node_modules/winax/index.d.ts` or the `winax` package's types) to determine:
- whether `release` exists as a free function (verified: yes — `export function release(...objects: any[]): void`)
- whether property writes go via assignment (`obj.prop = value`) or via a method call (verified: property writes use direct assignment on the proxy; the `[key: string]: any` index signature on `Object` class permits this)
- whether `invoke` returning a COM object yields the proxy directly or wraps it (verified: yes, returns the proxy as `unknown`)

Adjust the bridge accordingly. The key invariant: the bridge must surface the COM proxy as the return value of `invokeReturningObject` so the ReScript side can store it.

### Step 2 — Extend TsBridge externs

Add to `src/TsBridge.res`:

```rescript
@module("./Js/winaxBinding.mjs")
external winaxSetProperty: (TsWinaxModule.t, TsBridge.comObject, string, JSON.t) => unit = "setProperty"

@module("./Js/winaxBinding.mjs")
external winaxRelease: (TsWinaxModule.t, TsBridge.comObject) => unit = "release"

@module("./Js/winaxBinding.mjs")
external winaxInvokeReturningObject: (TsWinaxModule.t, TsBridge.comObject, string, array<JSON.t>) => TsBridge.comObject = "invokeReturningObject"
```

(Use whatever existing extern pattern is already in `TsBridge.res` — match the style. The externs above are illustrative.)

Also extend `Js/winaxBinding.mjs` (the `.mjs` wrapper, NOT the `.mts` source) to re-export the new functions if the .mjs file doesn't already forward them.

### Step 3 — Wire Winax.res

```rescript
let set: (...) => Promise.t<...> = (obj, property, value) => {
  _importWinax(()) -> Promise.then(m => {
    let rawMod = TsBridge.unwrapWinaxModule(m)
    TsBridge.winaxSetProperty(rawMod, obj, property, variantToJson(value))
    Promise.resolve(Ok())
  }) -> Promise.catch(...)
}

let release: ComInterfaces.comObject => unit = (obj) => {
  _importWinax(()) -> Promise.then(m => {
    TsBridge.winaxRelease(TsBridge.unwrapWinaxModule(m), obj)
    Promise.resolve()   // wrap to unit
  }) -> ignore
}

let getCount: ComInterfaces.comObject => Promise.t<result<int, Errors.t>> = (obj) => {
  get(obj, "Count") -> Promise.then(r => switch r {
    | Ok(JSON.Number(n)) => Promise.resolve(Ok(Float.toInt(n)))
    | Ok(JSON.String(s)) => Promise.resolve(Ok(Int.fromString(s)->Option.getOr(0)))
    | Ok(_) => Promise.resolve(Error(Errors.databaseError("Count not numeric")))
    | Error(e) => Promise.resolve(Error(e))
  })
}

let getItem: (ComInterfaces.comObject, ComInterfaces.variant) => Promise.t<result<ComInterfaces.comObject, Errors.t>> = (obj, idx) => {
  invoke(obj, "Item", [idx]) -> Promise.then(r => switch r {
    | Ok(json) =>
        // The invoke returns JSON.t, but we need comObject for collection items.
        // This is the FFI subtlety: collection items ARE COM objects, not JSON.
        // Solution: use a separate invokeReturningObject binding for Item.
        Promise.resolve(Error(Errors.databaseError("getItem: use invokeReturningObject for COM items")))
    | Error(e) => Promise.resolve(Error(e))
  })
}
```

For `getItem`: rather than dual APIs, add a separate helper in `Winax.res` for collection iteration that bypasses `invoke`:

```rescript
let invokeAsObject: (ComInterfaces.comObject, string, array<ComInterfaces.variant>) => Promise.t<result<ComInterfaces.comObject, Errors.t>> = ...
```

Document that `invoke` (returns JSON.t) is for methods returning data, while `invokeAsObject` (returns comObject) is for methods returning COM handles. Update `getItem` to use `invokeAsObject(obj, "Item", [idx])`.

### Step 4 — Make ComSession.open the DB

Replace `ComSession._connect` with a sequence that mirrors `wincom.py:178-232`:

```rescript
let _connect: (t, ~path: string, ~password: option<string>=?) => Promise.t<result<bool, Errors.t>> = (
  (session, ~path, ~password) => {
    // Step 1: file existence check
    if !Bindings.TsBridge.fileExists(path) {
      Promise.resolve(Error(Errors.fileNotFound(path)))
    } else {
      // Step 2: Access.Application
      Bindings.Winax.WINAX_BINDING.createObject("Access.Application")
        ->Promise.then(appResult => {
          switch appResult {
          | Error(e) => Promise.resolve(Error(e))
          | Ok(accessApp) => {
              session.handles.accessApp = Some(accessApp)

              // Step 3: Visible = False
              Bindings.Winax.WINAX_BINDING.set(accessApp, "Visible", ComInterfaces.VBool(false))
                ->Promise.then(_ => {
                  // Step 4: DBEngine
                  Bindings.Winax.WINAX_BINDING.get(accessApp, "DBEngine")
                    ->Promise.then(dbeResult => {
                      switch dbeResult {
                      | Error(e) => _rollback(accessApp, session); Promise.resolve(Error(e))
                      | Ok(_) =>
                          // Note: get() returns JSON.t; the DBEngine COM handle is a proxy
                          // embedded in the JSON wrapper. We need a binding that returns
                          // the raw comObject for the DBEngine.
                          //
                          // Workaround: use createObject("DAO.DBEngine.120") as Python does,
                          // since DAO.DBEngine.120 is a creatable progid and gives us the
                          // raw DBEngine handle independently.
                          Bindings.Winax.WINAX_BINDING.createObject("DAO.DBEngine.120")
                            ->Promise.then(daoDbEngineResult => {
                              switch daoDbEngineResult {
                              | Error(e) => _rollback(accessApp, session); Promise.resolve(Error(e))
                              | Ok(daoDbEngine) => {
                                  session.handles.daoDbEngine = Some(daoDbEngine)

                                  // Step 5: OpenDatabase (readwrite, false=readOnly, false=exclusive)
                                  let daoConnect = switch password {
                                    | Some(p) => ";PWD=" ++ p
                                    | None => ""
                                  }
                                  Bindings.Winax.WINAX_BINDING.invokeAsObject(
                                    daoDbEngine,
                                    "OpenDatabase",
                                    [ComInterfaces.VStr(path), ComInterfaces.VBool(false), ComInterfaces.VBool(false), ComInterfaces.VStr(daoConnect)]
                                  ) ->Promise.then(currentDbResult => {
                                    switch currentDbResult {
                                    | Error(e) => _rollback(accessApp, session); Promise.resolve(Error(e))
                                    | Ok(currentDb) => {
                                        session.handles.currentDb = Some(currentDb)

                                        // Step 6: OpenCurrentDatabase
                                        let openCurrArgs = switch password {
                                          | Some(p) => [ComInterfaces.VStr(path), ComInterfaces.VBool(false), ComInterfaces.VStr(p)]
                                          | None => [ComInterfaces.VStr(path), ComInterfaces.VBool(false)]
                                        }
                                        Bindings.Winax.WINAX_BINDING.invoke(accessApp, "OpenCurrentDatabase", openCurrArgs)
                                          ->Promise.then(ocdResult => {
                                            switch ocdResult {
                                            | Error(e) => _rollback(accessApp, session); Promise.resolve(Error(e))
                                            | Ok(_) => {
                                                // Step 7: DoCmd.SetWarnings(False) — best-effort
                                                _bestEffort(() => {
                                                  Bindings.Winax.WINAX_BINDING.get(accessApp, "DoCmd")
                                                  ->Promise.then(r => switch r {
                                                    | Ok(JSON.Object(o)) =>
                                                        // DoCmd.SetWarnings(false) — chained invoke
                                                        // (requires invoke on the DoCmd object)
                                                        Promise.resolve(Ok())
                                                    | _ => Promise.resolve(Error(Errors.databaseError("no DoCmd")))
                                                  })
                                                })

                                                // Step 8: ADODB.Connection — best-effort (existing pattern)
                                                Bindings.Winax.WINAX_BINDING.createObject("ADODB.Connection")
                                                  ->Promise.then(adoResult => {
                                                    switch adoResult {
                                                    | Error(_) => { session.handles.adoConn = None; session.isConnected = true; Promise.resolve(Ok(true)) }
                                                    | Ok(adoConn) => { session.handles.adoConn = Some(adoConn); session.isConnected = true; Promise.resolve(Ok(true)) }
                                                    }
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
                      }
                      })
                })
            }
          }
          })
    }
  }
)
```

Add `currentDb` and `daoDbEngine` to the session handle record (alongside existing `accessApp`, `daoDb`, `adoConn`). The existing `daoDb` field stays for backward compatibility or rename — decide based on the rest of the codebase that uses it (search for `handles.daoDb` and `handles.adoConn` usages).

Implement `_rollback(accessApp, session)` as a helper that releases everything acquired so far (in reverse order) and clears the fields.

Implement `_bestEffort(thunk)` that catches and logs but doesn't propagate errors.

### Step 5 — ComDataAdapter.connect delegates to ComSession

Replace `DaoAdapter.connect` to delegate:

```rescript
let connect = (self: t, dbPath: string, ~password: option<string>=?): Promise.t<result<bool, Errors.t>> => {
  if !_isWindows() {
    Promise.resolve(_platformError("COM automation requires Windows"))
  } else {
    if self.isConnected {
      Promise.resolve(Error(Errors.databaseError("Already connected")))
    } else {
      // Create or reuse session
      switch self.session {
      | None => self.session = Some(ComSession.make())
      | Some(_) => ()
      }
      let session = self.session->Option.getUnsafe
      ComSession.connect(session, ~path=dbPath, ~password=?password)
        ->Promise.then(result => {
          switch result {
          | Ok(b) =>
              self.isConnected = b
              self.dbPath = Some(dbPath)
              Promise.resolve(Ok(b))
          | Error(e) => Promise.resolve(Error(e))
          }
        })
    }
  }
}

let disconnect = (self: t): Promise.t<result<unit, Errors.t>> => {
  switch self.session {
  | None => Promise.resolve(Ok())
  | Some(session) =>
      ComSession.disconnect(session)
        ->Promise.then(r => {
          self.isConnected = false
          self.dbPath = None
          Promise.resolve(r)
        })
  }
}
```

Remove the duplicate dispatcher field from `comDataAdapterState` (now lives in `ComSession`). Keep `isConnected` and `dbPath` as cached views of session state for the adapter's `isConnected()` queries.

Update `comDataAdapterState` to add `mutable session: option<ComSession.t>` and drop `dispatcher`, `accessApp`, `daoDb` (now in ComSession).

### Step 6 — Tests

#### `test/ComSessionTest.res`

Add tests for:
- `connect` returns `Error(Errors.fileNotFound)` when path doesn't exist
- `connect` returns `Ok(true)` when path exists (fake `createObject`, `set`, `get`, `invokeAsObject`, `invoke`)
- `connect` rolls back partial state when `OpenDatabase` fails
- `connect` calls `SetWarnings(False)` and `OpenCurrentDatabase` (recorded calls)
- `disconnect` releases all handles in reverse order
- `disconnect` is idempotent

The fake pattern (likely `_recordingFake` or similar) is already in use — match it. Read `test/ComSessionTest.res` to understand the existing scaffolding before extending.

#### `test/ComDataAdapterTest.res` (extend)

Add tests for:
- `connect` delegates to `ComSession` (the adapter's `connect` is called → session's `connect` is called with the same path/password)
- `connect` returns `Error(Errors.databaseError("Already connected"))` when called twice
- `isConnected()` reflects session state
- `disconnect` delegates to `ComSession.disconnect`

#### `test/WinaxBindingTest.res` (new)

Tests:
- `WINAX_BINDING.set` calls the .mts `setProperty` and returns `Ok(())`
- `WINAX_BINDING.release` calls the .mts `release` and returns `unit`
- `WINAX_BINDING.getCount` reads `.Count` and parses Int
- `WINAX_BINDING.invokeAsObject` (new) returns the COM-object handle
- `WINAX_BINDING.getItem` (rewired) calls `.Item(idx)` and returns the COM-object handle

For unit-test purposes these can use a real winax stub or a fake COM object. Match the project's existing testing style for binding tests (likely a minimal `unit` returning fake — check `test/` for existing patterns; if none, look at how `Winax` is consumed in tests today).

### Step 7 — Verification

```bash
pnpm -C rescript-mcp clean
pnpm -C rescript-mcp build                       # exit 0
pnpm -C rescript-mcp test                        # 696+ pass (count may rise if new WinaxBindingTest added)
cd rescript-mcp && ACCESS_TEST_ASSUME_ACE=1 .venv/Scripts/python.exe -m pytest ../parity -m "not com_integration"
# Expect: 9/9 northwind unchanged, 16/17 fixture parity unchanged (1 pre-existing error remains)
git status --short                               # expected: only the new/modified files in scope + the untracked junk
git diff --stat 0391275..HEAD -- rescript-mcp/   # expected: only this plan's files
```

If parity numbers regress, STOP and investigate. If build fails due to a binding type mismatch, fix the extern, do not suppress.

### Step 8 — Stamp plan + update README

1. Append a "Final SHA" line at the bottom of this plan with the commit hash.
2. Edit `plans/README.md` row 028: change status from TODO to DONE, fill in the final SHA.
3. Commit the README update.

## Test plan

- Unit tests cover connect lifecycle (file-not-found, happy path, rollback on OpenDatabase failure, disconnect idempotency, double-connect rejection).
- Unit tests cover the new binding primitives (set, release, getCount, getItem, invokeAsObject).
- Integration test (optional but recommended): against the existing `tests/integration/fixtures/test_db.accdb` (Python fixture, shared with the ReScript parity harness) — connect, run `SELECT 1`, disconnect. Skip on non-Windows.
- Parity corpus: no regression. The COM Northwind corpus stays at its current state — it cannot improve until plans 029 (executeQuery) and 030 (schema reads) land. **Do not chase parity improvements in this plan.**

## Done criteria

- [ ] `ComSession._connect` actually opens the DAO database (verified by recorded calls in a fake-captured unit test).
- [ ] `ComDataAdapter.DaoAdapter.connect` delegates to `ComSession.connect` (no duplicate lifecycle logic remains in the adapter).
- [ ] `winaxBinding.mts` exports `setProperty`, `release`, `invokeReturningObject`. `Winax.res` exposes `set`, `release`, `getCount`, `getItem`, `invokeAsObject` as real implementations.
- [ ] All four previously-stubbed bindings have real implementations.
- [ ] `pnpm -C rescript-mcp clean && pnpm -C rescript-mcp build` exits 0.
- [ ] `pnpm -C rescript-mcp test` passes; existing 696 tests still green, new tests added pass.
- [ ] Parity: 9/9 northwind unchanged; 16/17 fixture parity unchanged.
- [ ] Drift check empty.
- [ ] Plan stamped with final SHA; `plans/README.md` row 028 marked DONE.
- [ ] Conventional commits; no AI attribution; no push; no PR.

## STOP conditions

- `rescript-mcp clean && pnpm -C rescript-mcp build` fails with errors you can't resolve in 2 attempts → STOP, report.
- Pre-existing tests fail (not your changes) → STOP, report the regression.
- The `set` change cascades into >3 unrelated test failures → STOP, report. Likely the `set` semantics change broke code that depended on it being a no-op.
- Connecting to a real `.accdb` triggers Access dialogs you can't dismiss (Windows-specific GUI test) → STOP, fall back to fake-captured unit tests, leave a maintenance note.
- Winax API differs from the bridge's assumption (e.g., no `release` exists) → STOP, report the winax shape discovered.

## Maintenance notes (for `plans/README.md` after done)

- Winax binding primitives are now real: `set`, `release`, `getCount`, `getItem`, `invokeAsObject`. Use `invoke` for data-returning methods, `invokeAsObject` for methods that return COM handles (OpenDatabase, OpenRecordset, CreateQueryDef, etc.).
- `ComSession` owns the COM lifecycle. `ComDataAdapter` and any future adapter go through `ComSession.connect`/`disconnect`.
- The `comDataAdapterState` record no longer holds COM handles directly — they live in `ComSession.handles`.
- `_formatValue` in `ComDataAdapter.res` still lacks datetime handling — that's plan 031's job.
