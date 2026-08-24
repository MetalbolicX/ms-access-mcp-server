// Interfaces.res — dependency-free implementation of record types + module types
// REQUIRED: this module must NOT import from Bindings/Odbc.res or reference the odbc package
// This module is the foundation for plans 004 (COM) and 005 (pooling)

// ---------------------------------------------------------------------------
// Result records
// ---------------------------------------------------------------------------

type queryResult = {
  success: bool,
  rows: array<dict<JSON.t>>,
  count: int,
  columns: array<string>,
  error: option<string>,
}

type mutationResult = {
  success: bool,
  affected: int,
  error: option<string>,
}

type ddlResult = {
  success: bool,
  error: option<string>,
}

// ---------------------------------------------------------------------------
// Schema records
// ---------------------------------------------------------------------------

type fieldInfo = {
  name: string,
  type_: string,  // @as "type"
  size: int,
  required: bool,
  allowZeroLength: bool,
  defaultValue: option<string>,
  isAutoincrement: bool,
}

type tableInfo = {
  name: string,
  fields: array<fieldInfo>,
  recordCount: int,
  primaryKey: option<array<string>>,
}

type queryInfo = {
  name: string,
  sql: string,
  type_: string,  // @as "type"
}

type relationshipInfo = {
  name: string,
  table: string,
  foreignTable: string,
  attributes: string,
  columns: array<string>,
  foreignColumns: array<string>,
}

type foreignKeyInfo = {
  name: string,
  columns: array<string>,
  foreignTable: string,
  foreignColumns: array<string>,
}

type indexInfo = {
  name: string,
  columns: array<string>,
  isUnique: bool,
  isPrimary: bool,
  ignoreNulls: bool,
}

type columnSchema = {
  name: string,
  sourceType: string,
  maxLength: option<int>,
  allowNull: bool,
  isAutoincrement: bool,
  defaultValue: option<string>,
}

type tableSchema = {
  name: string,
  columns: array<columnSchema>,
  primaryKey: option<array<string>>,
  foreignKeys: array<foreignKeyInfo>,
  indexes: array<indexInfo>,
}

type unknownMetadata = {
  primaryKeys: bool,
  foreignKeys: bool,
  defaults: bool,
  indexes: bool,
  autoincrement: bool,
}

// ---------------------------------------------------------------------------
// Adapter module types (signatures — implementations provide the actual behaviour)
// ---------------------------------------------------------------------------

module type DATA_ADAPTER = {
  type t

  let connect: (t, string, ~password: string=?) => Promise.t<result<bool, Errors.t>>
  let disconnect: t => Promise.t<result<unit, Errors.t>>
  let isConnected: t => Promise.t<result<bool, Errors.t>>

  let executeQuery: (t, string, ~params: array<JSON.t>=?) => Promise.t<result<queryResult, Errors.t>>
  let insertData: (t, string, dict<JSON.t>) => Promise.t<result<mutationResult, Errors.t>>
  let updateData: (t, string, dict<JSON.t>, ~where: option<JSON.t>=?) => Promise.t<result<mutationResult, Errors.t>>
  let deleteData: (t, string, ~where: option<JSON.t>=?) => Promise.t<result<mutationResult, Errors.t>>
  let executeRawSql: (t, string) => Promise.t<result<int, Errors.t>>
  let exportData: (t, string, string, ~format: option<string>=?, ~options: dict<JSON.t>=?) => Promise.t<result<mutationResult, Errors.t>>
}

module type SCHEMA_ADAPTER = {
  type t

  let connect: (t, string, ~password: string=?) => Promise.t<result<bool, Errors.t>>
  let disconnect: t => Promise.t<result<unit, Errors.t>>
  let isConnected: t => Promise.t<result<bool, Errors.t>>

  let getTables: t => Promise.t<result<array<tableInfo>, Errors.t>>
  let getSystemTables: t => Promise.t<result<array<tableInfo>, Errors.t>>
  let getObjectMetadata: (t, string) => Promise.t<result<dict<JSON.t>, Errors.t>>
  let getRelationships: t => Promise.t<result<array<relationshipInfo>, Errors.t>>
  let getTableSchemaPlan: t => Promise.t<result<(array<tableSchema>, unknownMetadata), Errors.t>>
  let generateSql: (t, string) => Promise.t<result<ddlResult, Errors.t>>
  let getDatabaseStatistics: t => Promise.t<result<dict<JSON.t>, Errors.t>>
  let getQueries: t => Promise.t<result<array<queryInfo>, Errors.t>>
  let createQuery: (t, string, string) => Promise.t<result<ddlResult, Errors.t>>
  let setQuerySql: (t, string, string) => Promise.t<result<ddlResult, Errors.t>>
  let deleteQuery: (t, string) => Promise.t<result<ddlResult, Errors.t>>
  let createTable: (t, string, array<columnSchema>) => Promise.t<result<ddlResult, Errors.t>>
  let deleteTable: (t, string) => Promise.t<result<ddlResult, Errors.t>>
  let alterTable: (t, string, array<dict<JSON.t>>) => Promise.t<result<dict<JSON.t>, Errors.t>>
  let getIndexes: (t, string) => Promise.t<result<array<indexInfo>, Errors.t>>
  let createIndex: (t, string, string, array<string>, ~unique: bool=?, ~ignoreNulls: bool=?) => Promise.t<result<ddlResult, Errors.t>>
  let dropIndex: (t, string, string) => Promise.t<result<ddlResult, Errors.t>>
  let createRelationship: (t, string, string, array<string>, string, array<string>) => Promise.t<result<ddlResult, Errors.t>>
  let deleteRelationship: (t, string, string) => Promise.t<result<ddlResult, Errors.t>>
}
