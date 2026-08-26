// BackendSelectorTest.res — tests for pure backend selection logic

open Test
open Services

// ---------------------------------------------------------------------------
// Helper to create capability list
// ---------------------------------------------------------------------------

let caps = (list: list<BackendSelector.backendCapability>): BackendSelector.capabilities => list

// ---------------------------------------------------------------------------
// Tests: explicit backend normalization
// ---------------------------------------------------------------------------

test("BackendSelector: ODBC explicit returns ODBC", () => {
  let result = BackendSelector.getAdapter(
    ~dbPath="/tmp/test.accdb",
    ~backend="ODBC",
    ~comAvailable=true,
  )
  switch result {
  | Ok(BackendSelector.ODBC) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("BackendSelector: COM explicit returns COM", () => {
  let result = BackendSelector.getAdapter(
    ~dbPath="/tmp/test.accdb",
    ~backend="COM",
    ~comAvailable=false,
  )
  switch result {
  | Ok(BackendSelector.COM) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("BackendSelector: DAO explicit returns DAO", () => {
  let result = BackendSelector.getAdapter(
    ~dbPath="/tmp/test.accdb",
    ~backend="DAO",
    ~comAvailable=true,
  )
  switch result {
  | Ok(BackendSelector.DAO) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("BackendSelector: lowercase normalized", () => {
  let result = BackendSelector.getAdapter(
    ~dbPath="/tmp/test.accdb",
    ~backend="odbc",
    ~comAvailable=true,
  )
  switch result {
  | Ok(BackendSelector.ODBC) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("BackendSelector: invalid backend returns error", () => {
  let result = BackendSelector.getAdapter(
    ~dbPath="/tmp/test.accdb",
    ~backend="invalid",
    ~comAvailable=true,
  )
  switch result {
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// Tests: AUTO resolution with comAvailable
// ---------------------------------------------------------------------------

test("BackendSelector: AUTO with comAvailable=true resolves to DAO", () => {
  let result = BackendSelector.getAdapter(
    ~dbPath="/tmp/test.accdb",
    ~comAvailable=true,
  )
  switch result {
  | Ok(BackendSelector.DAO) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("BackendSelector: AUTO with comAvailable=false resolves to ODBC", () => {
  let result = BackendSelector.getAdapter(
    ~dbPath="/tmp/test.accdb",
    ~comAvailable=false,
  )
  switch result {
  | Ok(BackendSelector.ODBC) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// Tests: AUTO resolution with VBA capability
// ---------------------------------------------------------------------------

test("BackendSelector: AUTO with CAN_HANDLE_VBA resolves to COM", () => {
  let result = BackendSelector.getAdapter(
    ~dbPath="/tmp/test.accdb",
    ~capabilities=caps(list{CAN_HANDLE_VBA}),
    ~comAvailable=false,
  )
  switch result {
  | Ok(BackendSelector.COM) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("BackendSelector: AUTO with CAN_HANDLE_FORMS resolves to COM", () => {
  let result = BackendSelector.getAdapter(
    ~dbPath="/tmp/test.accdb",
    ~capabilities=caps(list{CAN_HANDLE_FORMS}),
    ~comAvailable=false,
  )
  switch result {
  | Ok(BackendSelector.COM) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("BackendSelector: AUTO with CAN_HANDLE_REPORTS resolves to COM", () => {
  let result = BackendSelector.getAdapter(
    ~dbPath="/tmp/test.accdb",
    ~capabilities=caps(list{CAN_HANDLE_REPORTS}),
    ~comAvailable=false,
  )
  switch result {
  | Ok(BackendSelector.COM) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// Tests: ODBC conflicts with COM-only capabilities
// ---------------------------------------------------------------------------

test("BackendSelector: explicit ODBC with CAN_HANDLE_VBA returns error", () => {
  let result = BackendSelector.getAdapter(
    ~dbPath="/tmp/test.accdb",
    ~backend="ODBC",
    ~capabilities=caps(list{CAN_HANDLE_VBA}),
    ~comAvailable=true,
  )
  switch result {
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("BackendSelector: explicit ODBC with CAN_HANDLE_FORMS returns error", () => {
  let result = BackendSelector.getAdapter(
    ~dbPath="/tmp/test.accdb",
    ~backend="ODBC",
    ~capabilities=caps(list{CAN_HANDLE_FORMS}),
    ~comAvailable=true,
  )
  switch result {
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("BackendSelector: explicit ODBC with CAN_COMPACT returns error", () => {
  let result = BackendSelector.getAdapter(
    ~dbPath="/tmp/test.accdb",
    ~backend="ODBC",
    ~capabilities=caps(list{CAN_COMPACT}),
    ~comAvailable=true,
  )
  switch result {
  | Error(_) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// Tests: COM-only capabilities don't affect non-ODBC backends
// ---------------------------------------------------------------------------

test("BackendSelector: explicit COM with CAN_HANDLE_VBA succeeds", () => {
  let result = BackendSelector.getAdapter(
    ~dbPath="/tmp/test.accdb",
    ~backend="COM",
    ~capabilities=caps(list{CAN_HANDLE_VBA}),
    ~comAvailable=false,
  )
  switch result {
  | Ok(BackendSelector.COM) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("BackendSelector: explicit DAO with CAN_READ_DATA succeeds", () => {
  let result = BackendSelector.getAdapter(
    ~dbPath="/tmp/test.accdb",
    ~backend="DAO",
    ~capabilities=caps(list{CAN_READ_DATA}),
    ~comAvailable=true,
  )
  switch result {
  | Ok(BackendSelector.DAO) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// Tests: AUTO with non-COM-only capabilities follows comAvailable
// ---------------------------------------------------------------------------

test("BackendSelector: AUTO with CAN_READ_DATA follows comAvailable=true", () => {
  let result = BackendSelector.getAdapter(
    ~dbPath="/tmp/test.accdb",
    ~capabilities=caps(list{CAN_READ_DATA, CAN_WRITE_DATA}),
    ~comAvailable=true,
  )
  switch result {
  | Ok(BackendSelector.DAO) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

test("BackendSelector: AUTO with CAN_READ_DATA follows comAvailable=false", () => {
  let result = BackendSelector.getAdapter(
    ~dbPath="/tmp/test.accdb",
    ~capabilities=caps(list{CAN_READ_DATA}),
    ~comAvailable=false,
  )
  switch result {
  | Ok(BackendSelector.ODBC) => assertion(~operator="equal", (a, b) => a == b, true, true)
  | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})
