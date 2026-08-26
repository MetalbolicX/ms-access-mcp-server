// Instances.res — adapter instance record types
// Field order is a FROZEN SEAM CONTRACT (REQ-CROSS-2).
// These types are derived from the live DATA_ADAPTER (9 ops) and
// SCHEMA_ADAPTER (22 ops) module types in Interfaces.res.
// NOTE: insertData takes JSON.t per live OdbcAdapter (NOT dict<JSON.t>
// per the stale Interfaces declaration — interface drift tracked separately).

open Interfaces

// ---------------------------------------------------------------------------
// Type aliases — keep in sync with Interfaces.res
// ---------------------------------------------------------------------------

type queryResult = Interfaces.queryResult
type mutationResult = Interfaces.mutationResult
type tableInfo = Interfaces.tableInfo
type relationshipInfo = Interfaces.relationshipInfo
type tableSchema = Interfaces.tableSchema
type unknownMetadata = Interfaces.unknownMetadata
type ddlResult = Interfaces.ddlResult
type queryInfo = Interfaces.queryInfo
type columnSchema = Interfaces.columnSchema
type indexInfo = Interfaces.indexInfo

// ---------------------------------------------------------------------------
// dataAdapterInstance — 9-field record-of-closures (record type, not class)
// ---------------------------------------------------------------------------

type dataAdapterInstance = {
  connect: (string, ~password: string=?) => Promise.t<result<bool, Errors.t>>,
  disconnect: unit => Promise.t<result<unit, Errors.t>>,
  isConnected: unit => Promise.t<result<bool, Errors.t>>,
  executeQuery: (string, ~params: array<JSON.t>=?) => Promise.t<result<queryResult, Errors.t>>,
  insertData: (string, JSON.t) => Promise.t<result<mutationResult, Errors.t>>,
  updateData: (string, dict<JSON.t>, ~where: option<JSON.t>=?) => Promise.t<result<mutationResult, Errors.t>>,
  deleteData: (string, ~where: option<JSON.t>=?) => Promise.t<result<mutationResult, Errors.t>>,
  executeRawSql: string => Promise.t<result<int, Errors.t>>,
  exportData: (string, string, ~format: option<string>=?, ~options: option<dict<JSON.t>>=?) => Promise.t<result<mutationResult, Errors.t>>,
}

// ---------------------------------------------------------------------------
// schemaAdapterInstance — 22-field record-of-closures (record type, not class)
// ---------------------------------------------------------------------------

type schemaAdapterInstance = {
  connect: (string, ~password: string=?) => Promise.t<result<bool, Errors.t>>,
  disconnect: unit => Promise.t<result<unit, Errors.t>>,
  isConnected: unit => Promise.t<result<bool, Errors.t>>,
  getTables: unit => Promise.t<result<array<tableInfo>, Errors.t>>,
  getSystemTables: unit => Promise.t<result<array<tableInfo>, Errors.t>>,
  getObjectMetadata: string => Promise.t<result<dict<JSON.t>, Errors.t>>,
  getRelationships: unit => Promise.t<result<array<relationshipInfo>, Errors.t>>,
  getTableSchemaPlan: unit => Promise.t<result<(array<tableSchema>, unknownMetadata), Errors.t>>,
  generateSql: string => Promise.t<result<ddlResult, Errors.t>>,
  getDatabaseStatistics: unit => Promise.t<result<dict<JSON.t>, Errors.t>>,
  getQueries: unit => Promise.t<result<array<queryInfo>, Errors.t>>,
  createQuery: (string, string) => Promise.t<result<ddlResult, Errors.t>>,
  setQuerySql: (string, string) => Promise.t<result<ddlResult, Errors.t>>,
  deleteQuery: string => Promise.t<result<ddlResult, Errors.t>>,
  createTable: (string, array<columnSchema>) => Promise.t<result<ddlResult, Errors.t>>,
  deleteTable: string => Promise.t<result<ddlResult, Errors.t>>,
  alterTable: (string, array<dict<JSON.t>>) => Promise.t<result<dict<JSON.t>, Errors.t>>,
  getIndexes: string => Promise.t<result<array<indexInfo>, Errors.t>>,
  createIndex: (string, string, array<string>, ~unique: bool=?, ~ignoreNulls: bool=?) => Promise.t<result<ddlResult, Errors.t>>,
  dropIndex: (string, string) => Promise.t<result<ddlResult, Errors.t>>,
  createRelationship: (string, string, array<string>, string, array<string>) => Promise.t<result<ddlResult, Errors.t>>,
  deleteRelationship: (string, string) => Promise.t<result<ddlResult, Errors.t>>,
}
