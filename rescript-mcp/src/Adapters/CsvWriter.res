// CsvWriter.res — RFC-4180 CSV serialization
// slice-3e

// ---------------------------------------------------------------------------
// _needsQuoting — does field require quoting per RFC-4180?
// Must quote if contains: " (double-quote), , (comma), CR, or LF
// ---------------------------------------------------------------------------

let _needsQuoting = (field: string): bool => {
  String.includes(field, "\"") ||
    String.includes(field, ",") ||
    String.includes(field, "\r") ||
    String.includes(field, "\n")
}

// ---------------------------------------------------------------------------
// escapeField — RFC-4180: escape embedded double-quotes by doubling
// Returns the escaped content WITHOUT surrounding quotes.
// Called only when field is already known to need quoting.
// ---------------------------------------------------------------------------

let escapeField = (field: string): string => {
  field->Js.String2.split("")->Belt.Array.map(c => {
    if c == "\"" { "\"\"" } else { c }
  })->Belt.Array.reduce("", (acc, c) => acc ++ c)
}

// ---------------------------------------------------------------------------
// serializeRow — produce a single CSV line
// Default delimiter is comma; accepts semicolon, tab, etc.
// ---------------------------------------------------------------------------

let serializeRow = (fields: array<string>, ~delimiter: string=","): string => {
  if Belt.Array.length(fields) == 0 {
    ""
  } else {
    let rec loop = (i: int, ~acc: string): string => {
      if i >= Belt.Array.length(fields) {
        acc
      } else {
        let field = Belt.Array.getUnsafe(fields, i)
        let escaped = _needsQuoting(field) ? "\"" ++ escapeField(field) ++ "\"" : field
        let newAcc = i == 0 ? escaped : acc ++ delimiter ++ escaped
        loop(i + 1, ~acc=newAcc)
      }
    }
    loop(0, ~acc="")
  }
}

// ---------------------------------------------------------------------------
// serializeRows — join multiple rows with CRLF (no trailing CRLF)
// ---------------------------------------------------------------------------

let serializeRows = (rows: array<array<string>>, ~delimiter: string=","): string => {
  if Belt.Array.length(rows) == 0 {
    ""
  } else {
    let rec loop = (i: int, ~acc: string): string => {
      if i >= Belt.Array.length(rows) {
        acc
      } else {
        let row = Belt.Array.getUnsafe(rows, i)
        let line = serializeRow(row, ~delimiter)
        let newAcc = i == 0 ? line : acc ++ "\r\n" ++ line
        loop(i + 1, ~acc=newAcc)
      }
    }
    loop(0, ~acc="")
  }
}

// ---------------------------------------------------------------------------
// serializeWithHeaders — header row first, then all data rows
// ---------------------------------------------------------------------------

let serializeWithHeaders = (
  headers: array<string>,
  rows: array<array<string>>,
  ~delimiter: string=",",
): string => {
  let headerLine = serializeRow(headers, ~delimiter)
  let dataLines = serializeRows(rows, ~delimiter)
  if dataLines == "" {
    headerLine
  } else {
    headerLine ++ "\r\n" ++ dataLines
  }
}
