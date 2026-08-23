// Adapters.res — re-export wrapper to make Adapters a top-level module
// The Adapters directory contains Interfaces, SqlBuilder, OdbcSchemaReader, etc.
// In ReScript, a directory must have a <name>.res file to be a module.
module Interfaces = Interfaces
module SqlBuilder = SqlBuilder
module OdbcAdapter = OdbcAdapter
module OdbcSchemaReader = OdbcSchemaReader
module CsvWriter = CsvWriter
