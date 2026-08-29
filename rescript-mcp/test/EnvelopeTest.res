open Test

// T4 RED test — Mcp/Envelope transcribe: Facade dict → MCP response envelope
// Tests: dict with success:true/false/absent → isError bool, content array

// ---------------------------------------------------------------------------
// Test helper: get first element from array (safe, since we check length first)
// ---------------------------------------------------------------------------

let getFirst: array<'a> => option<'a> = arr => Array.get(arr, 0)

// ---------------------------------------------------------------------------
// T4.1 — {success: true, rows: [...]} → isError: false, content with JSON text
// ---------------------------------------------------------------------------

test("transcribe: success:true dict returns isError:false with JSON content", () => {
  let input: dict<JSON.t> = dict{
    "success": JSON.Boolean(true),
    "rows": JSON.Array([JSON.Object(dict{"id": JSON.Number(1.0)})]),
  }

  let result = Mcp.Envelope.transcribe(JSON.Object(input))

  assertion(~operator="equal", (a, b) => a == b, result.isError, false)
  assertion(~operator="equal", (a, b) => a == b, Array.length(result.content), 1)
  switch getFirst(result.content) {
  | Some(block) => {
      assertion(~operator="equal", (a, b) => a == b, block.type_, "text")
      let containsSuccess = String.includes(block.text, "\"success\":true") || String.includes(block.text, "\"success\": true")
      assertion(~operator="equal", (a, b) => a == b, containsSuccess, true)
    }
  | None => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// T4.2 — {success: false, error: "..."} → isError: true, content with JSON text
// ---------------------------------------------------------------------------

test("transcribe: success:false dict returns isError:true with JSON content", () => {
  let input: dict<JSON.t> = dict{
    "success": JSON.Boolean(false),
    "error": JSON.String("Not connected to database"),
  }

  let result = Mcp.Envelope.transcribe(JSON.Object(input))

  assertion(~operator="equal", (a, b) => a == b, result.isError, true)
  assertion(~operator="equal", (a, b) => a == b, Array.length(result.content), 1)
  switch getFirst(result.content) {
  | Some(block) => {
      assertion(~operator="equal", (a, b) => a == b, block.type_, "text")
      let containsError = String.includes(block.text, "Not connected to database")
      assertion(~operator="equal", (a, b) => a == b, containsError, true)
    }
  | None => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// T4.3 — {success: true, dry_run: true, sql: "..."} → isError: false
// (dry-run is NOT an error — it passes through with isError:false)
// ---------------------------------------------------------------------------

test("transcribe: dry_run:true dict returns isError:false (not treated as error)", () => {
  let input: dict<JSON.t> = dict{
    "success": JSON.Boolean(true),
    "dry_run": JSON.Boolean(true),
    "sql": JSON.String("SELECT 1"),
  }

  let result = Mcp.Envelope.transcribe(JSON.Object(input))

  assertion(~operator="equal", (a, b) => a == b, result.isError, false)
  assertion(~operator="equal", (a, b) => a == b, Array.length(result.content), 1)
  switch getFirst(result.content) {
  | Some(block) => assertion(~operator="equal", (a, b) => a == b, block.type_, "text")
  | None => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// T4.4 — Empty dict {} → isError:false (defensive default)
// ---------------------------------------------------------------------------

test("transcribe: empty dict returns isError:false with '{}' text", () => {
  let input: dict<JSON.t> = dict{}

  let result = Mcp.Envelope.transcribe(JSON.Object(input))

  assertion(~operator="equal", (a, b) => a == b, result.isError, false)
  assertion(~operator="equal", (a, b) => a == b, Array.length(result.content), 1)
  switch getFirst(result.content) {
  | Some(block) => {
      assertion(~operator="equal", (a, b) => a == b, block.type_, "text")
      assertion(~operator="equal", (a, b) => a == b, block.text, "{}")
    }
  | None => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})

// ---------------------------------------------------------------------------
// T4.5 — Nested complex dict → JSON.stringify preserves structure
// ---------------------------------------------------------------------------

test("transcribe: nested complex dict preserves all fields in JSON text", () => {
  let input: dict<JSON.t> = dict{
    "success": JSON.Boolean(true),
    "rows": JSON.Array([
      JSON.Object(dict{
        "id": JSON.Number(1.0),
        "name": JSON.String("Alice"),
      }),
      JSON.Object(dict{
        "id": JSON.Number(2.0),
        "name": JSON.String("Bob"),
      }),
    ]),
    "count": JSON.Number(2.0),
    "columns": JSON.Array([JSON.String("id"), JSON.String("name")]),
  }

  let result = Mcp.Envelope.transcribe(JSON.Object(input))

  assertion(~operator="equal", (a, b) => a == b, result.isError, false)
  assertion(~operator="equal", (a, b) => a == b, Array.length(result.content), 1)
  switch getFirst(result.content) {
  | Some(block) => {
      assertion(~operator="equal", (a, b) => a == b, block.type_, "text")
      let hasRows = String.includes(block.text, "\"rows\"")
      let hasCount = String.includes(block.text, "\"count\"")
      let hasColumns = String.includes(block.text, "\"columns\"")
      let hasNames = String.includes(block.text, "Alice") && String.includes(block.text, "Bob")
      assertion(~operator="equal", (a, b) => a == b, hasRows && hasCount && hasColumns && hasNames, true)
    }
  | None => assertion(~operator="equal", (a, b) => a == b, false, true)
  }
})
