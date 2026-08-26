// odbcDecode.mts — typed static-ESM bridge for raw node-odbc value decoding.
// Decodes plain JS values from node-odbc into typed DTOs at the FFI boundary.
// Pure TypeScript; no ReScript, no side-effects.

// DTO kind tags — mirrors oDBcValue variants in Bindings/Odbc.resi
export type ValueKind =
  | "null"
  | "bool"
  | "int"
  | "float"
  | "str"
  | "date"
  | "buffer"
  | "unknown"

// DTO: each raw ODBC cell is tagged with its runtime type
export interface ValueDto {
  kind: ValueKind
  value?: unknown // string for str, number for int/float, boolean for bool, string (ISO) for date, string (base64) for buffer
}

// Decode a raw node-odbc cell value into a typed DTO.
// Returns {kind: "unknown"} for unrecognized types — caller maps to Error(DatabaseError(...))
export const decodeValue = (v: unknown): ValueDto => {
  if (v === null || v === undefined) {
    return { kind: "null" }
  }
  if (typeof v === "boolean") {
    return { kind: "bool", value: v }
  }
  if (typeof v === "number") {
    // Integral numbers → Int; non-integral → Float
    // NaN and Infinity treated as float
    if (Number.isInteger(v) && !isNaN(v)) {
      return { kind: "int", value: v }
    }
    return { kind: "float", value: v }
  }
  if (typeof v === "string") {
    return { kind: "str", value: v }
  }
  if (v instanceof Date) {
    return { kind: "date", value: v.toISOString() }
  }
  if (Buffer.isBuffer(v)) {
    return { kind: "buffer", value: v.toString("base64") }
  }
  // Unknown: plain objects, arrays, symbols, functions, etc.
  return { kind: "unknown" }
}

// Decode an array of raw row values (from node-odbc columns order) into ValueDto array.
export const decodeRow = (values: unknown[]): ValueDto[] =>
  values.map(decodeValue)

// Decode all rows: array of arrays (node-odbc native row format) → array of ValueDto arrays.
export const decodeRows = (nativeRows: unknown[][]): ValueDto[][] =>
  nativeRows.map(decodeRow)
