// OdbcImportDynamicTest.res — RED test pinning the _importOdbc fix.
//
// Plan 021 step 3 — before the fix, `external _importOdbc: unit => Promise.t<...> = "import"`
// compiled to a method call (`Odbc.import()`) that does not exist on the
// `odbc` CJS namespace. Calling Bindings.Odbc.connect triggered the real
// dynamic-import path and threw `TypeError: Odbc.import is not a function`.
//
// After the fix (dynamic `import("odbc")` via %raw), the inner promise
// resolves and `connect` returns Ok(_) or Error(_) — never throws.

open Test

testAsync("_importOdbc: dynamic import resolves without throwing TypeError", cb => {
  // Use a path that cannot exist so the connect promise resolves (not hangs)
  Bindings.Odbc.connect("DBQ=C:\\nonexistent\\notreal.accdb")
    ->Promise.then(r => {
      switch r {
      | Ok(_) | Error(_) => {
          assertion(~operator="equal", (a, b) => a == b, true, true)
          cb(~planned=1, ())
        }
      }
      Promise.resolve()
    })
    ->Promise.catch(_e => {
      // Currently the bug throws TypeError before the connect call returns;
      // after the fix, this catch should never fire (the inner Promise resolves).
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->ignore
})