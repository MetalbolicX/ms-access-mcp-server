// InstancesPlaceholderTest.res — GREEN: Instances module is now present
// Verifies the dataAdapterInstance record type is well-formed.
open Test
open Adapters
open Interfaces

test("Instances dataAdapterInstance has correct 9 fields", () => {
  // Build a value of the instance type to verify all fields are present and well-typed
  let instance: Instances.dataAdapterInstance = {
    connect: (_connStr, ~password=?) => Promise.resolve(Ok(true)),
    disconnect: () => Promise.resolve(Ok()),
    isConnected: () => Promise.resolve(Ok(false)),
    executeQuery: (_sql, ~params=?) =>
      Promise.resolve(Ok({success: true, rows: [], count: 0, columns: [], error: None})),
    insertData: (_t, _d) =>
      Promise.resolve(Ok({success: true, affected: 0, error: None})),
    updateData: (_t, _d, ~where=?) =>
      Promise.resolve(Ok({success: true, affected: 0, error: None})),
    deleteData: (_t, ~where=?) =>
      Promise.resolve(Ok({success: true, affected: 0, error: None})),
    executeRawSql: (_s) => Promise.resolve(Ok(0)),
    exportData: (_q, _p, ~format=?, ~options=?) =>
      Promise.resolve(Ok({success: true, affected: 0, error: None})),
  }
  // Verify connect is callable (compile proof of well-formedness)
  let _ = instance.connect("DBQ=test")
  assertion(~operator="equal", (a, b) => a == b, true, true)
})
