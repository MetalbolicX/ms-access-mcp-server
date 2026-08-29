open Test
open Adapters.CsvWriter

// Task 3.5 RED tests — CsvWriter pure serializer
// RFC-4180 CSV serialization

// ---------------------------------------------------------------------------
// serializeRow — single CSV row
// ---------------------------------------------------------------------------

test("serializeRow plain field unchanged", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    serializeRow(["Hello", "World"]),
    "Hello,World",
  )
})

test("serializeRow field with comma is quoted", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    serializeRow(["Hello, World"]),
    "\"Hello, World\"",
  )
})

test("serializeRow field with double-quote doubles it", () => {
  // Field: Say "Hello" → quoted, embedded " doubled → "Say ""Hello"""
  // In string literal: "\\\"Say \\\"\\\"Hello\\\"\\\"\\\"\\\"\\""
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    serializeRow(["Say \"Hello\""]),
    "\"Say \"\"Hello\"\"\"",
  )
})

test("serializeRow field with CR is quoted", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    serializeRow(["Line1\rLine2"]),
    "\"Line1\rLine2\"",
  )
})

test("serializeRow field with LF is quoted", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    serializeRow(["Line1\nLine2"]),
    "\"Line1\nLine2\"",
  )
})

test("serializeRow empty input array produces empty line", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    serializeRow([]),
    "",
  )
})

test("serializeRow mixed special chars all escaped", () => {
  // A, "B"\nC → quoted with embedded " doubled → "A, ""B""<LF>C"
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    serializeRow(["A, \"B\"\nC"]),
    "\"A, \"\"B\"\"\nC\"",
  )
})

// ---------------------------------------------------------------------------
// serializeRow with custom delimiter
// ---------------------------------------------------------------------------

test("serializeRow semicolon delimiter", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    serializeRow(["Name", "Value"], ~delimiter=";"),
    "Name;Value",
  )
})

test("serializeRow tab delimiter", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    serializeRow(["Col1", "Col2"], ~delimiter="\t"),
    "Col1\tCol2",
  )
})

test("serializeRow semicolon with comma field is quoted", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    serializeRow(["A, B"], ~delimiter=";"),
    "\"A, B\"",
  )
})

// ---------------------------------------------------------------------------
// serializeRows — multiple rows joined with CRLF
// ---------------------------------------------------------------------------

test("serializeRows joins rows with CRLF", () => {
  let rows: array<array<string>> = [
    ["Name", "City"],
    ["Alice", "Boston"],
    ["Bob", "Chicago"],
  ]
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    serializeRows(rows),
    "Name,City\r\nAlice,Boston\r\nBob,Chicago",
  )
})

test("serializeRows empty array produces empty string", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    serializeRows([]),
    "",
  )
})

test("serializeRows single row no trailing CRLF", () => {
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    serializeRows([["Solo"]]),
    "Solo",
  )
})

// ---------------------------------------------------------------------------
// serializeWithHeaders — header row first, then data rows
// ---------------------------------------------------------------------------

test("serializeWithHeaders header line first", () => {
  let headers = ["ID", "Name"]
  let rows: array<array<string>> = [
    ["1", "Alice"],
    ["2", "Bob"],
  ]
  let result = serializeWithHeaders(headers, rows)
  let lines = result->String.split("\r\n")
  assertion(~operator="equal", (a, b) => a == b, Array.get(lines, 0), Some("ID,Name"))
  assertion(~operator="equal", (a, b) => a == b, Array.get(lines, 1), Some("1,Alice"))
  assertion(~operator="equal", (a, b) => a == b, Array.get(lines, 2), Some("2,Bob"))
  assertion(~operator="equal", (a, b) => a == b, Array.get(lines, 3), None)
})

test("serializeWithHeaders empty rows only header line", () => {
  let headers = ["X", "Y"]
  let result = serializeWithHeaders(headers, [])
  assertion(
    ~operator="equal",
    (a, b) => a == b,
    result,
    "X,Y",
  )
})

// ---------------------------------------------------------------------------
// Round-trip sanity — known CSV string is output of serializer
// ---------------------------------------------------------------------------

test("round-trip known CSV matches expected output", () => {
  let headers = ["City", "Population"]
  let rows: array<array<string>> = [
    ["New York, NY", "8.3M"],
    ["Jane \"J\" Doe", "100"],
    ["Line1\nLine2", "Alt"],
  ]
  let csv = serializeWithHeaders(headers, rows)
  // City,Population<CRLF>"New York, NY",8.3M<CRLF>"Jane ""J"" Doe",100<CRLF>"Line1<LF>Line2",Alt
  let expected = "City,Population\r\n\"New York, NY\",8.3M\r\n\"Jane \"\"J\"\" Doe\",100\r\n\"Line1\nLine2\",Alt"
  assertion(~operator="equal", (a, b) => a == b, csv, expected)
})
