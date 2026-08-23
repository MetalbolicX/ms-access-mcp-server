// SqlBuilder.resi — pure SQL + param builders interface
// REQ-D4/D5/D6/D9 + REQ-S7/S8

type whereClause =
  | Dict(dict<JSON.t>)
  | Raw(string)

// columnInfo describes a column for DDL generation
type columnInfo = {
  name: string,
  colType: string,
  size: int,
  nullable: bool,
}

// alterTableAction represents a single ALTER TABLE sub-operation
type alterTableAction =
  | AddColumn(columnInfo)
  | DropColumn(string)
  | ModifyColumn(columnInfo)
  | RenameTable(string)
  | RenameColumn(string, string)

let bracket: string => string
let paramPlaceholders: int => string
let whereFromDict: dict<JSON.t> => (string, array<JSON.t>)
let whereFromRaw: (string, dict<JSON.t>) => result<string, Errors.t>
let insert: (string, dict<JSON.t>) => (string, array<JSON.t>)
let update: (string, dict<JSON.t>, option<whereClause>) => (string, array<JSON.t>)
let delete: (string, option<whereClause>) => (string, array<JSON.t>)
let odbcTypeMap: string => string
let columnDef: columnInfo => string
let createTable: (string, array<columnInfo>) => string
let dropTable: string => string
let alterTable: (string, alterTableAction) => option<string>
let createIndex: (~name: string, ~table: string, ~columns: array<string>, ~unique: bool, ~ignore_nulls: bool=?) => string
let dropIndex: (~name: string, ~table: string) => string
let createRelationship: (
  ~relationshipName: string,
  ~table: string,
  ~columns: array<string>,
  ~foreignTable: string,
  ~foreignColumns: array<string>,
) => result<string, Errors.t>
let deleteRelationship: (~table: string, ~relationshipName: string) => string
let createView: (~name: string, ~sql: string) => string
let dropView: (~name: string) => string
let setView: (~name: string, ~sql: string) => result<(string, string), Errors.t>
