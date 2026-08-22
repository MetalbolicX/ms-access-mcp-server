// SqlBuilder.resi — pure SQL + param builders interface
// REQ-D4/D5/D6/D9

type whereClause =
  | Dict(dict<JSON.t>)
  | Raw(string)

let bracket: string => string
let paramPlaceholders: int => string
let whereFromDict: dict<JSON.t> => (string, array<JSON.t>)
let whereFromRaw: (string, dict<JSON.t>) => result<string, Errors.t>
let insert: (string, dict<JSON.t>) => (string, array<JSON.t>)
let update: (string, dict<JSON.t>, option<whereClause>) => (string, array<JSON.t>)
let delete: (string, option<whereClause>) => (string, array<JSON.t>)
