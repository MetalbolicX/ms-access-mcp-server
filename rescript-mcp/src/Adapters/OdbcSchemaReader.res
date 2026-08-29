// OdbcSchemaReader.res — pure MSysRelationships reader
// REQ-S4 / D6 — verbatim SQL, grouping, deterministic naming, degrade-to-[]
//
// Type for bucket entries from Object.entries (JS interop)
// tuple: [string, [array<string>, array<string>]]
type bucketEntry = (string, (array<string>, array<string>))

// issueQuery — the query-issuance seam (matches .resi)
type issueQuery = (~sql: string) => Promise.t<result<array<dict<JSON.t>>, Errors.t>>

// ---------------------------------------------------------------------------
// MSysRelationships query — exact oracle per odbc_schema_reader.py:20-26
// ---------------------------------------------------------------------------

let _MSYS_RELATIONSHIPS_SQL = "SELECT szColumn, szObject, szReferencedObject, szReferencedColumn FROM MSysRelationships WHERE szObject IS NOT NULL AND szReferencedObject IS NOT NULL ORDER BY szObject, szReferencedObject, szColumn"

// ---------------------------------------------------------------------------
// _dictGet — safe JSON.t extraction from dict (no exceptions)
// ---------------------------------------------------------------------------

let _dictGet = (d: dict<JSON.t>, k: string): option<JSON.t> => {
  Dict.get(d, k)
}

// ---------------------------------------------------------------------------
// _jsonToString — extract string from JSON.t, default ""
// ---------------------------------------------------------------------------

let _jsonToString = (j: option<JSON.t>): string => {
  switch j {
  | Some(JSON.String(s)) => s
  | _ => ""
  }
}

// ---------------------------------------------------------------------------
// _getEntries — JS interop to get Object.entries as a typed array
// ---------------------------------------------------------------------------

let _getEntries: (dict<(array<string>, array<string>)>) => array<bucketEntry> = %raw(
  "d => Object.entries(d)"
)

// ---------------------------------------------------------------------------
// _groupRows — pure grouping of MSysRelationships rows into RelationshipInfo
// Rows arrive one per (FK column, PK column) pair; multi-column FKs produce
// multiple rows with the same (child, parent) which are merged here.
// ---------------------------------------------------------------------------

// Bucket key: "parentTable|childTable" string (FK naming uses parent_child order)
let _bucketKey = (child: string, parent: string): string => parent ++ "|" ++ child

let _groupRows = (rows: array<dict<JSON.t>>): array<Interfaces.relationshipInfo> => {
  // buckets: "child|parent" → (columns, foreign_columns)
  let buckets: ref<dict<(array<string>, array<string>)>> = ref(dict{})

  // Accumulate rows into buckets (mutable, in-place)
  Array.forEach(rows, row => {
    let szObject = _jsonToString(_dictGet(row, "szObject"))
    let szColumn = _jsonToString(_dictGet(row, "szColumn"))
    let szReferencedObject = _jsonToString(_dictGet(row, "szReferencedObject"))
    let szReferencedColumn = _jsonToString(_dictGet(row, "szReferencedColumn"))

    if szObject != "" && szReferencedObject != "" {
      let key = _bucketKey(szObject, szReferencedObject)  // (child, parent) → parent|child
      switch Dict.get(buckets.contents, key) {
      | Some((cols, fcols)) => {
          let newCols = Array.concat(cols, [szColumn])
          let newFcols = Array.concat(fcols, [szReferencedColumn])
          let _ = Dict.set(buckets.contents, key, (newCols, newFcols))
          ()
        }
      | None => {
          let _ = Dict.set(buckets.contents, key, ([szColumn], [szReferencedColumn]))
          ()
        }
      }
    } else {
      ()
    }
  })

  // Convert buckets to RelationshipInfo array
  // Explicitly sort keys for deterministic output (Object.entries order is not guaranteed)
  let sortedKeys: array<string> = %raw("Object.keys(buckets.contents).sort()")
  let results: array<Interfaces.relationshipInfo> = Array.map(
    sortedKeys,
    (key) => {
      let (columns, foreignColumns) = switch Dict.get(buckets.contents, key) {
      | Some(v) => v
      | None => ([], [])
      }
      let parts = String.split(key, "|")
      let parentTable = switch Array.get(parts, 0) {
        | Some(p) => p
        | None => ""
      }
      let childTable = switch Array.get(parts, 1) {
        | Some(p) => p
        | None => ""
      }
      let rel: Interfaces.relationshipInfo = {
        name: "FK_" ++ childTable ++ "_" ++ parentTable,
        table: childTable,
        foreignTable: parentTable,
        attributes: "",
        columns: columns,
        foreignColumns: foreignColumns,
      }
      rel
    }
  )
  results
}

// ---------------------------------------------------------------------------
// readRelationships — public API
// Issues MSysRelationships query, groups results, degrades to Ok([]) on error
// ---------------------------------------------------------------------------

let readRelationships = (
  ~query: issueQuery,
): Promise.t<result<array<Interfaces.relationshipInfo>, Errors.t>> => {
  query(~sql=_MSYS_RELATIONSHIPS_SQL)
    ->Promise.then(result => {
      switch result {
      | Error(e) => {
          // Query failed (hidden/denied MSysRelationships) — degrade gracefully
          // Uses Logging.warn for the warning (mirrors python odbc_schema_reader.py)
          let _ = Logging.warn("get_relationships via MSysRelationships failed: " ++ Errors.toDict(e).message)
          Promise.resolve(Ok([]))
        }
      | Ok(rows) => {
          let relationships = _groupRows(rows)
          Promise.resolve(Ok(relationships))
        }
      }
    })
}
