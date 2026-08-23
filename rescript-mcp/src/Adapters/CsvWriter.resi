// CsvWriter.resi — RFC-4180 CSV serialization interface
// slice-3e

let escapeField: string => string
let serializeRow: (array<string>, ~delimiter: string=?) => string
let serializeRows: (array<array<string>>, ~delimiter: string=?) => string
let serializeWithHeaders: (array<string>, array<array<string>>, ~delimiter: string=?) => string
