// SqlBuilder.res — pure SQL + param builders
// REQ-D4/D5/D6/D9

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
