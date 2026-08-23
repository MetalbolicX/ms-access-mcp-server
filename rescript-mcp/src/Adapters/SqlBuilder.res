// SqlBuilder.res — pure SQL + param builders
// REQ-D4/D5/D6/D9 + REQ-S7/S8

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

// whereClause represents the optional WHERE clause for UPDATE/DELETE
type whereClause =
  | Dict(dict<JSON.t>)
  | Raw(string)

// ---------------------------------------------------------------------------
// _strJoin — join array<string> with separator
// ---------------------------------------------------------------------------

let _strJoin = (arr: array<string>, sep: string): string => {
  if Belt.Array.length(arr) == 0 {
    ""
  } else {
    let rec loop = (i: int, ~acc: string) => {
      if i >= Belt.Array.length(arr) {
        acc
      } else {
        let ith = Belt.Array.getUnsafe(arr, i)
        let newAcc = acc == "" ? ith : acc ++ sep ++ ith
        loop(i + 1, ~acc=newAcc)
      }
    }
    loop(0, ~acc="")
  }
}

// ---------------------------------------------------------------------------
// _bracketEscape — global replace of ] → ]] using %raw
// Python: name.replace("]", "]]") — global replace all occurrences
// ---------------------------------------------------------------------------

let _bracketEscape = (name: string): string => {
  %raw("n => n.replace(/]/g, ']]')")(name)
}

// ---------------------------------------------------------------------------
// bracket — wrap identifier in square brackets, escape embedded ]
// Python: "[" + name.replace("]", "]]") + "]"
// ---------------------------------------------------------------------------

let bracket = (name: string): string => {
  "[" ++ _bracketEscape(name) ++ "]"
}

// ---------------------------------------------------------------------------
// paramPlaceholders — generate (?, ?, ...) for INSERT VALUES
// Python: "(" + ", ".join(["?"] * count) + ")"
// ---------------------------------------------------------------------------

let paramPlaceholders = (count: int): string => {
  if count <= 0 {
    "()"
  } else {
    let parts = Belt.Array.make(count, "?")
    "(" ++ _strJoin(parts, ", ") ++ ")"
  }
}

// ---------------------------------------------------------------------------
// _rawWhitelist — pre-compiled regex for raw WHERE validation (D5)
// Pattern: ^[\w\s.,=<>()'"%\-]+$
// Allows: word chars, whitespace, dots, commas, operators, parens, quotes, %, dash
// Rejects: \ ] [ ; -- /* */ ` and other SQL injection vectors
// ---------------------------------------------------------------------------

let _rawWhitelist: RegExp.t = %re("/^[\w\s.,=<>()'\"%-]+$/")

// ---------------------------------------------------------------------------
// _sqlCommentPatterns — regexes for SQL comment / injection patterns
// Checked BEFORE whitelist; presence of these is always an error
// Use %raw with new RegExp() to avoid regex-literal parsing issues with /* and */
// ---------------------------------------------------------------------------

let _dashDash: RegExp.t = %raw("new RegExp('--')")
let _slashSlashStar: RegExp.t = %raw("new RegExp('\\\\/\\\\*')")
let _starSlash: RegExp.t = %raw("new RegExp('\\\\*\\\\/')")

// ---------------------------------------------------------------------------
// _regexTest — test string against precompiled regex
// ---------------------------------------------------------------------------

let _regexTest = (str: string, re: RegExp.t): bool => {
  %raw(" (s, r) => r.test(s) ")(str, re)
}

// ---------------------------------------------------------------------------
// whereFromDict — dict → condition part + ordered params
// Returns condition only (no "WHERE" prefix) — callers prepend as needed
// Used by update/delete when the WHERE clause comes purely from dict
// ---------------------------------------------------------------------------

let whereFromDict = (dict: dict<JSON.t>): (string, array<JSON.t>) => {
  let entries: array<(string, JSON.t)> = %raw("d => Object.entries(d)")(dict)
  let len = Belt.Array.length(entries)
  if len == 0 {
    ("", [])
  } else {
    let parts = Belt.Array.make(len, "")
    let params: array<JSON.t> = Belt.Array.make(len, JSON.Null)
    let _ = Belt.Array.forEachWithIndex(entries, (i, entry) => {
      let (key, value) = entry
      parts[i] = bracket(key) ++ " = ?"
      params[i] = value
    })
    (_strJoin(parts, " AND "), params)
  }
}

// ---------------------------------------------------------------------------
// whereFromRaw — validate raw string, merge with dict conditions
// Returns "WHERE <condition>" or Error. Never returns bare condition.
// - dict empty: returns "WHERE <raw>"  (standalone call from tools)
// - dict non-empty: returns "WHERE <dict_cond> AND <raw>"  (merged call)
// Callers (update/delete) should NOT prepend "WHERE" when result starts with "WHERE"
// ---------------------------------------------------------------------------

let whereFromRaw = (raw: string, dict: dict<JSON.t>): result<string, Errors.t> => {
  // First reject SQL comment/injection patterns (D5)
  if _regexTest(raw, _dashDash) || _regexTest(raw, _slashSlashStar) || _regexTest(raw, _starSlash) {
    Error(Errors.validationError("where_dict string contains disallowed characters"))
  } else if !_regexTest(raw, _rawWhitelist) {
    // Then check whitelist of allowed characters
    Error(Errors.validationError("where_dict string contains disallowed characters"))
  } else {
    let entries: array<(string, JSON.t)> = %raw("d => Object.entries(d)")(dict)
    let len = Belt.Array.length(entries)
    if len == 0 {
      // dict empty: return standalone "WHERE <raw>"
      Ok("WHERE " ++ raw)
    } else {
      // dict non-empty: build dict conditions, append raw
      let parts = Belt.Array.make(len, "")
      let _ = Belt.Array.forEachWithIndex(entries, (i, entry) => {
        let (key, _value) = entry
        parts[i] = bracket(key) ++ " = ?"
      })
      // Returns "WHERE <dict_cond> AND <raw>" — "WHERE" always present
      Ok("WHERE " ++ _strJoin(parts, " AND ") ++ " AND " ++ raw)
    }
  }
}

// ---------------------------------------------------------------------------
// insert — INSERT INTO [table] (col, ...) VALUES (?, ...)
// Columns and params in insertion order
// ---------------------------------------------------------------------------

let insert = (table: string, record: dict<JSON.t>): (string, array<JSON.t>) => {
  let entries: array<(string, JSON.t)> = %raw("d => Object.entries(d)")(record)
  let len = Belt.Array.length(entries)
  if len == 0 {
    ("INSERT INTO " ++ bracket(table) ++ " () VALUES ()", [])
  } else {
    let cols = Belt.Array.map(entries, entry => {
      let (key, _) = entry
      bracket(key)
    })
    let params = Belt.Array.map(entries, entry => {
      let (_key, value) = entry
      value
    })
    let colList = _strJoin(cols, ", ")
    let placeholders = paramPlaceholders(len)
    ("INSERT INTO " ++ bracket(table) ++ " (" ++ colList ++ ") VALUES " ++ placeholders, params)
  }
}

// ---------------------------------------------------------------------------
// _buildSetClause — build "SET col = ?, ..." from dict
// Returns (setClause, params) where params is array<JSON.t>
// ---------------------------------------------------------------------------

let _buildSetClause = (table: string, setDict: dict<JSON.t>): (string, array<JSON.t>) => {
  let entries: array<(string, JSON.t)> = %raw("d => Object.entries(d)")(setDict)
  let len = Belt.Array.length(entries)
  if len == 0 {
    ("UPDATE " ++ bracket(table), [])
  } else {
    let parts = Belt.Array.map(entries, entry => {
      let (key, _value) = entry
      bracket(key) ++ " = ?"
    })
    let params = Belt.Array.map(entries, entry => {
      let (_key, value) = entry
      value
    })
    ("UPDATE " ++ bracket(table) ++ " SET " ++ _strJoin(parts, ", "), params)
  }
}

// ---------------------------------------------------------------------------
// update — UPDATE [table] SET col = ?, ... [WHERE ...]
// Params order: SET values first, then WHERE values
// None WHERE = unconditional update (no WHERE clause at all)
// ---------------------------------------------------------------------------

let update = (table: string, setDict: dict<JSON.t>, whereClause: option<whereClause>): (string, array<JSON.t>) => {
  let (baseClause, setParams) = _buildSetClause(table, setDict)
  switch whereClause {
  | None => (baseClause, setParams)
  | Some(Dict(d)) => {
      // Pure dict WHERE — build and prepend "WHERE "
      let (whereCond, whereParams) = whereFromDict(d)
      if whereCond == "" {
        (baseClause, setParams)
      } else {
        (baseClause ++ " WHERE " ++ whereCond, Belt.Array.concat(setParams, whereParams))
      }
    }
  | Some(Raw(raw)) => {
      // Raw WHERE — use raw string directly as the full WHERE clause
      // Python behavior: string WHERE replaces dict conditions entirely
      // dict values go to SET only; raw string becomes the WHERE as-is
      // NOTE: if raw is invalid, we still prepend "WHERE " (caller must validate)
      (baseClause ++ " WHERE " ++ raw, setParams)
    }
  }
}

// ---------------------------------------------------------------------------
// delete — DELETE FROM [table] [WHERE ...]
// None WHERE = unconditional delete (D9 parity — no WHERE clause at all)
// ---------------------------------------------------------------------------

let delete = (table: string, whereClause: option<whereClause>): (string, array<JSON.t>) => {
  let base = "DELETE FROM " ++ bracket(table)
  switch whereClause {
  | None => (base, [])
  | Some(Dict(d)) => {
      let (whereCond, whereParams) = whereFromDict(d)
      if whereCond == "" {
        (base, [])
      } else {
        (base ++ " WHERE " ++ whereCond, whereParams)
      }
    }
  | Some(Raw(raw)) => {
      // whereFromRaw handles empty dict: returns "WHERE <raw>"
      switch whereFromRaw(raw, dict{}) {
      | Error(_) => (base ++ " WHERE " ++ raw, [])
      | Ok(whereFull) => (base ++ " " ++ whereFull, [])
      }
    }
  }
}

// ---------------------------------------------------------------------------
// DDL types — column info and alter-table actions (REQ-S7/S8)
// ---------------------------------------------------------------------------

// columnInfo describes a column for DDL generation
type columnInfo = {
  name: string,
  colType: string,  // Access type name (e.g. "Text", "Long Integer")
  size: int,        // 0 means "use default"
  nullable: bool,
}

// alterTableAction represents a single ALTER TABLE sub-operation
type alterTableAction =
  | AddColumn(columnInfo)
  | DropColumn(string)
  | ModifyColumn(columnInfo)
  | RenameTable(string)   // returns None (ODBC unsupported)
  | RenameColumn(string, string)  // old, new — returns None (ODBC unsupported)

// ---------------------------------------------------------------------------
// odbcTypeMap — Access type → ODBC SQL type name (REQ-S7)
// Case-insensitive; empty/unknown → passthrough
// ---------------------------------------------------------------------------

let odbcTypeMap = (accessType: string): string => {
  // Handle "INTEGER" (SQL standard, all-caps) before case-insensitive pass
  switch accessType {
  | "INTEGER" => "INT"
  | _ => {
      let t: string = %raw("(s) => (s ?? '').toLowerCase()")(accessType)
      switch t {
      | "" => ""
      | "text" => "VARCHAR"
      | "varchar" => "VARCHAR"
      | "char" => "VARCHAR"
      | "memo" => "TEXT"
      | "long integer" => "INT"
      | "integer" => "SMALLINT"  // Access "Integer" type (2-byte)
      | "int" => "INT"
      | "bigint" => "BIGINT"
      | "smallint" => "SMALLINT"
      | "tinyint" => "TINYINT"
      | "bit" => "BIT"
      | "boolean" => "BIT"
      | "date/time" => "DATETIME"
      | "datetime" => "DATETIME"
      | "date" => "DATETIME"
      | "time" => "DATETIME"
      | "timestamp" => "DATETIME"
      | "decimal" => "DECIMAL"
      | "numeric" => "DECIMAL"
      | "money" => "MONEY"
      | "currency" => "MONEY"
      | "float" => "FLOAT"
      | "double" => "FLOAT"
      | "real" => "REAL"
      | "single" => "REAL"
      | "binary" => "VARBINARY"
      | "varbinary" => "VARBINARY"
      | "image" => "VARBINARY"
      | "guid" => "GUID"
      | _ => "VARCHAR"  // unknown types default to VARCHAR
      }
    }
  }
}

// ---------------------------------------------------------------------------
// _columnDefInternal — build a single column def string (private helper)
// Returns "[name] TYPE[size] [NOT] NULL"
// ---------------------------------------------------------------------------

let _columnDefInternal = (col: columnInfo): string => {
  let odbcType = odbcTypeMap(col.colType)
  let size = if col.size > 0 { col.size } else { 255 }
  let typed = if odbcType == "" {
    ""
  } else if odbcType == "VARCHAR" || odbcType == "CHAR" {
    // VARCHAR/CHAR: append size (default 255)
    odbcType ++ "(" ++ Belt.Int.toString(size) ++ ")"
  } else {
    // TEXT (MEMO) and all other types: no size suffix
    odbcType
  }
  let nullable = if col.nullable { "NULL" } else { "NOT NULL" }
  bracket(col.name) ++ " " ++ typed ++ " " ++ nullable
}

// ---------------------------------------------------------------------------
// columnDef — public column definition (exports same logic as _columnDefInternal)
// ---------------------------------------------------------------------------

let columnDef = _columnDefInternal

// ---------------------------------------------------------------------------
// createTable — CREATE TABLE [...] (...) (REQ-S7)
// ---------------------------------------------------------------------------

let createTable = (table: string, columns: array<columnInfo>): string => {
  let colDefs = Belt.Array.map(columns, _columnDefInternal)
  let colsStr = _strJoin(colDefs, ", ")
  "CREATE TABLE " ++ bracket(table) ++ " (" ++ colsStr ++ ")"
}

// ---------------------------------------------------------------------------
// dropTable — DROP TABLE [...] (REQ-S7)
// ---------------------------------------------------------------------------

let dropTable = (table: string): string => {
  "DROP TABLE " ++ bracket(table)
}

// ---------------------------------------------------------------------------
// alterTable — ALTER TABLE [...] action (REQ-S8)
// Returns Some(sql) for supported ops; None for rename ops (ODBC unsupported)
// ---------------------------------------------------------------------------

let alterTable = (table: string, action: alterTableAction): option<string> => {
  switch action {
  | AddColumn(col) => Some("ALTER TABLE " ++ bracket(table) ++ " ADD COLUMN " ++ _columnDefInternal(col))
  | DropColumn(colName) => Some("ALTER TABLE " ++ bracket(table) ++ " DROP COLUMN " ++ bracket(colName))
  | ModifyColumn(col) => Some("ALTER TABLE " ++ bracket(table) ++ " ALTER COLUMN " ++ _columnDefInternal(col))
  | RenameTable(_) => None  // ODBC does not support rename_table
  | RenameColumn(_, _) => None  // ODBC does not support rename_column
  }
}

// ---------------------------------------------------------------------------
// createIndex — CREATE [UNIQUE] INDEX ... ON ... (col, ...) (REQ-S7)
// unique=false → basic index; unique=true → CREATE UNIQUE INDEX
// Columns are always bracket-escaped
// ---------------------------------------------------------------------------

let createIndex = (~name: string, ~table: string, ~columns: array<string>, ~unique: bool, ~ignore_nulls: bool=false): string => {
  let uniqueKw = if unique { "UNIQUE INDEX" } else { "INDEX" }
  let colList = _strJoin(Belt.Array.map(columns, c => "[" ++ _bracketEscape(c) ++ "]"), ", ")
  let base = "CREATE " ++ uniqueKw ++ " [" ++ _bracketEscape(name) ++ "] ON [" ++ _bracketEscape(table) ++ "] (" ++ colList ++ ")"
  if unique && ignore_nulls {
    base ++ " WITH IGNORE NULL"
  } else {
    base
  }
}

// ---------------------------------------------------------------------------
// dropIndex — DROP INDEX ... ON ... (REQ-S7)
// Required ON clause per Access/Jet DDL syntax
// ---------------------------------------------------------------------------

let dropIndex = (~name: string, ~table: string): string => {
  "DROP INDEX [" ++ _bracketEscape(name) ++ "] ON [" ++ _bracketEscape(table) ++ "]"
}

// ---------------------------------------------------------------------------
// createRelationship — ALTER TABLE ADD CONSTRAINT FK (REQ-S7)
// Access/Jet stores relationships via ALTER TABLE ADD CONSTRAINT
// Validates: relationship name ≤ 64 chars, child table ≤ 64 chars
// ---------------------------------------------------------------------------

let createRelationship = (
  ~relationshipName: string,
  ~table: string,
  ~columns: array<string>,
  ~foreignTable: string,
  ~foreignColumns: array<string>,
): result<string, Errors.t> => {
  if Belt.Array.length(columns) != Belt.Array.length(foreignColumns) {
    Error(Errors.validationError("columns and foreign_columns must have same length"))
  } else if String.length(relationshipName) > 64 {
    Error(Errors.validationError("Relationship name exceeds 64 characters"))
  } else if String.length(table) > 64 {
    Error(Errors.validationError("Child table name exceeds 64 characters"))
  } else {
    let colList = _strJoin(Belt.Array.map(columns, c => "[" ++ _bracketEscape(c) ++ "]"), ", ")
    let foreignColList = _strJoin(Belt.Array.map(foreignColumns, fc => "[" ++ _bracketEscape(fc) ++ "]"), ", ")
    Ok(
      "ALTER TABLE [" ++ _bracketEscape(table) ++
      "] ADD CONSTRAINT [" ++ _bracketEscape(relationshipName) ++
      "] FOREIGN KEY (" ++ colList ++ ") REFERENCES [" ++
      _bracketEscape(foreignTable) ++ "] (" ++ foreignColList ++ ")"
    )
  }
}

// ---------------------------------------------------------------------------
// deleteRelationship — ALTER TABLE DROP CONSTRAINT (REQ-S7)
// ---------------------------------------------------------------------------

let deleteRelationship = (~table: string, ~relationshipName: string): string => {
  "ALTER TABLE [" ++ _bracketEscape(table) ++ "] DROP CONSTRAINT [" ++ _bracketEscape(relationshipName) ++ "]"
}

// ---------------------------------------------------------------------------
// createView — CREATE VIEW [name] AS sql (REQ-S6)
// sql is used verbatim; only the view name is bracket-escaped
// ---------------------------------------------------------------------------

let createView = (~name: string, ~sql: string): string => {
  "CREATE VIEW " ++ bracket(name) ++ " AS " ++ sql
}

// ---------------------------------------------------------------------------
// dropView — DROP VIEW [name] (REQ-S6)
// ---------------------------------------------------------------------------

let dropView = (~name: string): string => {
  "DROP VIEW " ++ bracket(name)
}

// ---------------------------------------------------------------------------
// setView — DROP VIEW + CREATE VIEW pair (REQ-S6)
// Returns Ok((dropSql, createSql)) so caller can execute both statements
// ---------------------------------------------------------------------------

let setView = (~name: string, ~sql: string): result<(string, string), Errors.t> => {
  Ok((dropView(~name), createView(~name, ~sql)))
}
