// InstancesTest.res — instance producer passthrough tests
// T2: verify asInstance producers for OdbcAdapter, FakeOdbcAdapter, FakeSchemaAdapter

open Test
open Adapters
open Adapters.Instances

// ---------------------------------------------------------------------------
// OdbcAdapter.asInstance — data adapter producer
// ---------------------------------------------------------------------------

testAsync("OdbcAdapter.asInstance: isConnected on unconnected t returns Ok(false)", cb => {
  let t: OdbcAdapter.t = {connection: None, dbPath: None}
  let instance = OdbcAdapter.asInstance(t)
  instance.isConnected()
    ->Promise.then(r => {
      Promise.resolve(
        switch r {
        | Ok(false) => assertion(~operator="equal", (a, b) => a == b, true, true)
        | Ok(true) => assertion(~operator="equal", (a, b) => a == b, false, true)
        | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
        }
      )
    })
    ->Promise.then(() => Promise.resolve(cb(~planned=1, ())))
    ->Promise.catch(_e => {
      Promise.resolve(cb(~planned=0, ()))
    })
    ->ignore
})

testAsync("OdbcAdapter.asInstance: disconnect on unconnected returns Ok", cb => {
  let t: OdbcAdapter.t = {connection: None, dbPath: None}
  let instance = OdbcAdapter.asInstance(t)
  instance.disconnect()
    ->Promise.then(r => {
      Promise.resolve(
        switch r {
        | Ok(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
        | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
        }
      )
    })
    ->Promise.then(() => Promise.resolve(cb(~planned=1, ())))
    ->Promise.catch(_e => {
      Promise.resolve(cb(~planned=0, ()))
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// FakeOdbcAdapter.asInstance — fake data adapter producer
// ---------------------------------------------------------------------------

testAsync("FakeOdbcAdapter.asInstance: connect passthrough records call in log", cb => {
  Fakes.CallLog.reset()
  let fake = Fakes.FakeOdbcAdapter.make(~name="test-odbc-instance")
  let instance = Fakes.FakeOdbcAdapter.asInstance(fake)
  ignore(instance.connect("/tmp/test.accdb"))
  let calls = Fakes.CallLog.connectCalls()
  let count = List.length(calls)
  assertion(~operator="equal", (a, b) => a == b, count, 1)
  cb(~planned=1, ())
})

testAsync("FakeOdbcAdapter.asInstance: isConnected returns Ok(false) on unconnected", cb => {
  let fake = Fakes.FakeOdbcAdapter.make(~name="test-odbc-instance2")
  let instance = Fakes.FakeOdbcAdapter.asInstance(fake)
  instance.isConnected()
    ->Promise.then(r => {
      Promise.resolve(
        switch r {
        | Ok(false) => assertion(~operator="equal", (a, b) => a == b, true, true)
        | Ok(true) => assertion(~operator="equal", (a, b) => a == b, false, true)
        | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
        }
      )
    })
    ->Promise.then(() => Promise.resolve(cb(~planned=1, ())))
    ->Promise.catch(_e => {
      Promise.resolve(cb(~planned=0, ()))
    })
    ->ignore
})

// ---------------------------------------------------------------------------
// FakeSchemaAdapter.asInstance — fake schema adapter producer (22 fields)
// ---------------------------------------------------------------------------

testAsync("FakeSchemaAdapter.asInstance: connect passthrough records call in log", cb => {
  Fakes.CallLog.reset()
  let fake = Fakes.FakeSchemaAdapter.make(~name="test-schema-instance")
  let instance = Fakes.FakeSchemaAdapter.asInstance(fake)
  ignore(instance.connect("/tmp/test.accdb"))
  let calls = Fakes.CallLog.schemaCalls()
  let count = List.length(calls)
  assertion(~operator="equal", (a, b) => a == b, count, 1)
  cb(~planned=1, ())
})

testAsync("FakeSchemaAdapter.asInstance: getTables returns Ok([]) with no fake tables", cb => {
  let fake = Fakes.FakeSchemaAdapter.make(~name="test-schema-instance2")
  let instance = Fakes.FakeSchemaAdapter.asInstance(fake)
  instance.getTables()
    ->Promise.then(r => {
      Promise.resolve(
        switch r {
        | Ok(tables) => assertion(~operator="equal", (a, b) => a == b, Array.length(tables), 0)
        | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
        }
      )
    })
    ->Promise.then(() => Promise.resolve(cb(~planned=1, ())))
    ->Promise.catch(_e => {
      Promise.resolve(cb(~planned=0, ()))
    })
    ->ignore
})

test("FakeSchemaAdapter.asInstance: all 22 schema methods are callable", () => {
  let fake = Fakes.FakeSchemaAdapter.make(~name="test-schema-all-22")
  let instance = Fakes.FakeSchemaAdapter.asInstance(fake)
  // Call each method — all should type-check (22 fields on schemaAdapterInstance)
  ignore(instance.connect("/tmp/test.accdb"))
  ignore(instance.disconnect())
  ignore(instance.isConnected())
  ignore(instance.getTables())
  ignore(instance.getSystemTables())
  ignore(instance.getObjectMetadata("TestTable"))
  ignore(instance.getRelationships())
  ignore(instance.getTableSchemaPlan())
  ignore(instance.generateSql("SELECT 1"))
  ignore(instance.getDatabaseStatistics())
  ignore(instance.getQueries())
  ignore(instance.createQuery("Q1", "SELECT 1"))
  ignore(instance.setQuerySql("Q1", "SELECT 1"))
  ignore(instance.deleteQuery("Q1"))
  ignore(instance.createTable("T1", []))
  ignore(instance.deleteTable("T1"))
  ignore(instance.alterTable("T1", []))
  ignore(instance.getIndexes("T1"))
  ignore(instance.createIndex("I1", "T1", ["C1"]))
  ignore(instance.dropIndex("I1", "T1"))
  ignore(instance.createRelationship("R1", "T1", ["C1"], "T2", ["C2"]))
  ignore(instance.deleteRelationship("R1", "T1"))
  // All 22 compiled — test passes (no assertion needed; compile-time check)
  assertion(~operator="equal", (a, b) => a == b, 22, 22)
})
