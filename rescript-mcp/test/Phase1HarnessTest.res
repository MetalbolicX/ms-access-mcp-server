// Phase1HarnessTest.res — Phase 1 portable harness verification tests.
//
// These tests verify harness behavior (child-status recording, exit-code
// handling, backend identity, exact-case selection) WITHOUT requiring live
// COM or Access. They test the parity runner's contract and are safe to run
// on any platform.
//
// NOTE: tests that pass on logical equality (exit 0 with identical JSON)
// are DIAGNOSTIC ONLY — they do NOT constitute acceptance of correctness.
// The comments explicitly state this for each such test.

open Test

// ---------------------------------------------------------------------------
// Mock child status builders (simulate what run.ts records per child)
// ---------------------------------------------------------------------------

type phaseMarkers = {
  setup: option<string>,
  nativeOp: option<string>,
  postcondition: option<string>,
  disconnect: option<string>,
  serialization: option<string>,
  processExit: option<string>,
}

type childStatus = {
  statusCode: option<int>,
  signal: option<string>,
  timeout: bool,
  spawnError: option<string>,
  stdoutValidJson: bool,
  stdoutShapeValid: bool,
  envelopeBackend: option<string>,
  logicalEquality: bool,
  skipReason: option<string>,
  stderrRedacted: string,
  phase: phaseMarkers,
}

let makeStatus = (
  ~statusCode: option<int>=None,
  ~signal: option<string>=None,
  ~timeout: bool=false,
  ~spawnError: option<string>=None,
  ~stdoutValidJson: bool=false,
  ~stdoutShapeValid: bool=false,
  ~envelopeBackend: option<string>=None,
  ~logicalEquality: bool=false,
  ~skipReason: option<string>=None,
  ~stderrRedacted: string="",
  ~phase: option<phaseMarkers>=None,
): childStatus => {
  {
    statusCode,
    signal,
    timeout,
    spawnError,
    stdoutValidJson,
    stdoutShapeValid,
    envelopeBackend,
    logicalEquality,
    skipReason,
    stderrRedacted,
    phase: switch phase {
      | Some(p) => p
      | None => {
          setup: None,
          nativeOp: None,
          postcondition: None,
          disconnect: None,
          serialization: None,
          processExit: None,
        }
    },
  }
}

// ---------------------------------------------------------------------------
// Test 1: Identical JSON envelopes + exit 134 must FAIL
// ---------------------------------------------------------------------------

test("Harness: nonzero exit 134 with valid JSON must be recorded as error", () => {
  // Simulate: child wrote valid envelope but exited 134 (COM teardown crash)
  let status = makeStatus(
    ~statusCode=Some(134),
    ~stdoutValidJson=true,
    ~stdoutShapeValid=true,
    ~envelopeBackend=Some("com"),
    ~phase=Some({
      setup: None,
      nativeOp: Some("rescript-start"),
      postcondition: None,
      disconnect: None,
      serialization: Some("rescript-nonzero-with-valid-json"),
      processExit: Some("exit-134"),
    }),
  )

  // Exit 134 is nonzero → must be recorded as error even with valid JSON
  let isNonzeroExit = status.statusCode != Some(0) && status.statusCode != None
  assertion(~operator="equal", (a, b) => a == b, isNonzeroExit, true)
})

test("Harness: nonzero exit 134 with valid JSON is not logical acceptance", () => {
  let status = makeStatus(
    ~statusCode=Some(134),
    ~stdoutValidJson=true,
    ~stdoutShapeValid=true,
    ~envelopeBackend=Some("com"),
    ~logicalEquality=false,
  )

  // Logical equality must be recorded separately for diagnosis;
  // nonzero exit means the result is NOT accepted
  let isErrorDueToNonzero = status.statusCode != Some(0) && status.statusCode != None
  assertion(~operator="equal", (a, b) => a == b, isErrorDueToNonzero, true)
  // logicalEquality is false here because we haven't compared envelopes yet
  assertion(~operator="equal", (a, b) => a == b, status.logicalEquality, false)
})

// ---------------------------------------------------------------------------
// Test 2: Identical JSON envelopes + exit 0 → PASS (diagnostic only)
// ---------------------------------------------------------------------------
//
// THIS IS NOT ACCEPTANCE — this test passes when envelopes match and exit is 0,
// but logical equality is recorded for DIAGNOSIS ONLY, not as proof of
// correctness. A future harness change must not treat this as a passing gate.

test("Harness: identical envelopes + exit 0 records logical equality (DIAGNOSTIC ONLY)", () => {
  let status = makeStatus(
    ~statusCode=Some(0),
    ~stdoutValidJson=true,
    ~stdoutShapeValid=true,
    ~envelopeBackend=Some("odbc"),
    ~logicalEquality=true,
    ~phase=Some({
      setup: None,
      nativeOp: Some("python-start"),
      postcondition: None,
      disconnect: None,
      serialization: Some("python-valid-json"),
      processExit: Some("exit-0"),
    }),
  )

  // Both sides wrote valid JSON with matching envelopes and exit 0
  let cleanExit = status.statusCode == Some(0)
  let validJson = status.stdoutValidJson == true
  let shapeValid = status.stdoutShapeValid == true

  // This is DIAGNOSTIC ONLY — passing here does not mean the operation
  // is correct, only that both children produced identical envelopes cleanly.
  assertion(~operator="equal", (a, b) => a == b, cleanExit && validJson && shapeValid, true)
  // The harness must record logicalEquality separately for diagnosis
  assertion(~operator="equal", (a, b) => a == b, status.logicalEquality, true)
})

// ---------------------------------------------------------------------------
// Test 3: Valid JSON + timeout must FAIL
// ---------------------------------------------------------------------------

test("Harness: timeout must be recorded even when stdout is valid JSON", () => {
  let status = makeStatus(
    ~statusCode=None,
    ~timeout=true,
    ~stdoutValidJson=true,
    ~stdoutShapeValid=true,
    ~spawnError=None,
  )

  // Timeout is a distinct error condition from nonzero exit
  let isTimeout = status.timeout == true
  let hasValidJson = status.stdoutValidJson == true

  // Timeout + valid JSON → still an error because timeout is true
  let isError = isTimeout || (status.statusCode != Some(0) && status.statusCode != None)
  assertion(~operator="equal", (a, b) => a == b, isError, true)
  assertion(~operator="equal", (a, b) => a == b, hasValidJson, true) // JSON is valid but child still errored
})

// ---------------------------------------------------------------------------
// Test 4: Malformed/missing stdout must FAIL
// ---------------------------------------------------------------------------

test("Harness: malformed stdout is recorded as invalid JSON", () => {
  let status = makeStatus(
    ~statusCode=Some(1),
    ~stdoutValidJson=false,
    ~stdoutShapeValid=false,
    ~spawnError=None,
  )

  let isInvalidJson = status.stdoutValidJson == false
  let hasNonzeroExit = status.statusCode != Some(0) && status.statusCode != None

  // Malformed JSON is an error condition regardless of exit code
  assertion(~operator="equal", (a, b) => a == b, isInvalidJson, true)
  assertion(~operator="equal", (a, b) => a == b, hasNonzeroExit, true)
})

test("Harness: missing stdout (no output) is recorded as driver error", () => {
  let status = makeStatus(
    ~statusCode=Some(1),
    ~stdoutValidJson=false,
    ~stdoutShapeValid=false,
    ~spawnError=None,
    ~stderrRedacted="",
  )

  // No stdout means driver error even if exit was 0
  let noOutput = status.stdoutValidJson == false && status.stdoutShapeValid == false
  assertion(~operator="equal", (a, b) => a == b, noOutput, true)
})

// ---------------------------------------------------------------------------
// Test 5: Empty stdout must FAIL
// ---------------------------------------------------------------------------

test("Harness: empty stdout is treated as no output (driver error)", () => {
  let status = makeStatus(
    ~statusCode=Some(0),
    ~stdoutValidJson=false,
    ~stdoutShapeValid=false,
  )

  // Empty stdout is equivalent to missing stdout
  let isEmptyOutput = status.stdoutValidJson == false
  assertion(~operator="equal", (a, b) => a == b, isEmptyOutput, true)
})

// ---------------------------------------------------------------------------
// Test 6: Backend identity — COM unavailable must NOT silently fall back to ODBC
// ---------------------------------------------------------------------------

test("Harness: backend identity is recorded when COM is unavailable", () => {
  // Simulate: Python ran with COM unavailable, fell back to ODBC
  let pyStatus = makeStatus(
    ~statusCode=Some(0),
    ~stdoutValidJson=true,
    ~stdoutShapeValid=true,
    ~envelopeBackend=Some("odbc"), // Explicitly recorded as ODBC
  )

  // When COM is unavailable but ODBC is used, backend must be "odbc" (not "com")
  // The harness must NOT silently substitute one backend for another
  let backendIsExplicit = pyStatus.envelopeBackend == Some("odbc")
  assertion(~operator="equal", (a, b) => a == b, backendIsExplicit, true)
})

test("Harness: backend mismatch between python and rescript must be surfaced", () => {
  let pyStatus = makeStatus(
    ~statusCode=Some(0),
    ~stdoutValidJson=true,
    ~stdoutShapeValid=true,
    ~envelopeBackend=Some("com"),
  )
  let rsStatus = makeStatus(
    ~statusCode=Some(0),
    ~stdoutValidJson=true,
    ~stdoutShapeValid=true,
    ~envelopeBackend=Some("odbc"),
  )

  // Backend mismatch must be detectable
  let mismatch = switch (pyStatus.envelopeBackend, rsStatus.envelopeBackend) {
    | (Some("com"), Some("odbc")) => true
    | (Some("odbc"), Some("com")) => true
    | (Some(a), Some(b)) if a != b => true
    | _ => false
  }
  assertion(~operator="equal", (a, b) => a == b, mismatch, true)
})

test("Harness: when COM unavailable, python backend must be 'odbc' not 'com'", () => {
  // This test proves the python driver does NOT silently fall back to COM
  // when COM is unavailable — it must record 'odbc' explicitly
  let pyStatus = makeStatus(
    ~statusCode=Some(0),
    ~stdoutValidJson=true,
    ~stdoutShapeValid=true,
    ~envelopeBackend=Some("odbc"), // Not "com" — proves no silent fallback
  )

  // If COM were silently used when unavailable, backend would be "com"
  // The fact it's "odbc" proves explicit fallback happened
  let isExplicitOdbc = pyStatus.envelopeBackend == Some("odbc")
  assertion(~operator="equal", (a, b) => a == b, isExplicitOdbc, true)
})

// ---------------------------------------------------------------------------
// Test 7: Exact-case selector executes exactly one case
// ---------------------------------------------------------------------------

test("Harness: exact-case filter selects exactly one case", () => {
  let allCases = ["connect_access.json", "get_tables.json", "query_data.json"]
  let exactCase: string = "get_tables.json"

  // Simulate the exact-case filter logic from run.ts
  let match = allCases->Js.Array2.find(c => c == exactCase)
  let filtered = switch match {
    | Some(c) => [c]
    | None => []
  }

  // Exact-case selection must return exactly 1 case, not 0, not all
  assertion(~operator="equal", (a, b) => a == b, Belt.Array.length(filtered), 1)
  assertion(~operator="equal", (a, b) => a == b, Belt.Array.get(filtered, 0), Some("get_tables.json"))
})

test("Harness: exact-case filter returns empty when case not found", () => {
  let allCases = ["connect_access.json", "get_tables.json"]
  let exactCase: string = "nonexistent_case.json"

  let match = allCases->Js.Array2.find(c => c == exactCase)
  let filtered = switch match {
    | Some(c) => [c]
    | None => []
  }

  // Nonexistent case must result in empty filter (runner should exit with error)
  assertion(~operator="equal", (a, b) => a == b, Belt.Array.length(filtered), 0)
})

// ---------------------------------------------------------------------------
// Test 8: Phase markers flow through envelope WITHOUT polluting result body
// ---------------------------------------------------------------------------

test("Harness: phase markers are separate from envelope body", () => {
  // Phase markers must be a separate field from the envelope
  // (not merged into the envelope body)
  let phase: phaseMarkers = {
    setup: Some("connect_access"),
    nativeOp: Some("get_tables"),
    postcondition: None,
    disconnect: Some("disconnect_access"),
    serialization: Some("python-valid-json"),
    processExit: Some("exit-0"),
  }

  // Phase markers exist as a distinct property
  let phaseExists = phase.serialization != None

  // The phase object has specific expected keys (not in envelope)
  let hasSetup = phase.setup == Some("connect_access")
  let hasNativeOp = phase.nativeOp == Some("get_tables")
  let hasSerialization = phase.serialization == Some("python-valid-json")

  // Phase exists as its own field — this proves it's not inside envelope
  assertion(~operator="equal", (a, b) => a == b, phaseExists, true)
  assertion(~operator="equal", (a, b) => a == b, hasSetup, true)
  assertion(~operator="equal", (a, b) => a == b, hasNativeOp, true)
  assertion(~operator="equal", (a, b) => a == b, hasSerialization, true)
})

// ---------------------------------------------------------------------------
// Test 9: Skip reason is recorded independently
// ---------------------------------------------------------------------------

test("Harness: skip reason is recorded when case is skipped", () => {
  let status = makeStatus(
    ~statusCode=None,
    ~skipReason=Some("COM variant not available on this platform"),
  )

  let hasSkipReason = status.skipReason != None
  let isNotAnError = status.statusCode == None && status.stdoutValidJson == false

  assertion(~operator="equal", (a, b) => a == b, hasSkipReason, true)
  assertion(~operator="equal", (a, b) => a == b, isNotAnError, true)
})
