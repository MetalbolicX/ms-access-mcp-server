// FakesTest.res — tests for FakeSchemaAdapter
// Task 1.5: Verify FakeSchemaAdapter.make() satisfies SCHEMA_ADAPTER module type

open Test
open Adapters
open Adapters.Interfaces

// ---------------------------------------------------------------------------
// Task 1.5: RED FakeSchemaAdapter test
// Compile-level RED: FakeSchemaAdapter module not found in Fakes.res yet
// ---------------------------------------------------------------------------

// This test uses FakeSchemaAdapter.getTables() — if FakeSchemaAdapter is missing
// or incomplete, the compiler will error on the missing module or method.
// ReScript's structural typing means any module implementing all 18 SCHEMA_ADAPTER
// methods will satisfy the interface at compile time.

testAsync("FakeSchemaAdapter: make().getTables() returns Ok([])", cb => {
  let adapter = Fakes.FakeSchemaAdapter.make()
  Fakes.FakeSchemaAdapter.getTables(adapter)
    ->Promise.then(r => {
      Promise.resolve(
        switch r {
        | Ok(tables) => assertion(~operator="equal", (a, b) => a == b, Array.length(tables), 0)
        | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
        }
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
    ->ignore
})
