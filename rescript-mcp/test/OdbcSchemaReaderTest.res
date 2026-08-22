open Test
open Adapters.OdbcSchemaReader

// Task 2.1 RED test — OdbcSchemaReader pure module
// REQ-S4 / D6 — MSysRelationships query, grouping, FK naming, graceful degradation

// ---------------------------------------------------------------------------
// Helpers — build a fake issueQuery from predefined rows
// ---------------------------------------------------------------------------

let makeFakeQuery = (rows: array<dict<JSON.t>>): issueQuery => {
  (~sql: string) => Promise.resolve(Ok(rows))
}

// ---------------------------------------------------------------------------
// readRelationships — main API
// ---------------------------------------------------------------------------

testAsync("readRelationships: executes verbatim MSysRelationships SQL", cb => {
  let capturedSql = ref("")
  let fakeQuery = (~sql: string) => {
    capturedSql.contents = sql
    Promise.resolve(Ok([]))
  }
  ignore(readRelationships(~query=fakeQuery)
    ->Promise.then(result => {
      let expected = "SELECT szColumn, szObject, szReferencedObject, szReferencedColumn FROM MSysRelationships WHERE szObject IS NOT NULL AND szReferencedObject IS NOT NULL ORDER BY szObject, szReferencedObject, szColumn"
      assertion(~operator="equal", (a, b) => a == b, capturedSql.contents, expected)
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("readRelationships: single FK row maps to correct RelationshipInfo shape", cb => {
  let fakeRows: array<dict<JSON.t>> = [
    dict{
      "szObject": JSON.String("Orders"),
      "szColumn": JSON.String("CustomerID"),
      "szReferencedObject": JSON.String("Customers"),
      "szReferencedColumn": JSON.String("ID"),
    },
  ]
  ignore(readRelationships(~query=makeFakeQuery(fakeRows))
    ->Promise.then(result => {
      switch result {
      | Ok(rels) => {
          assertion(~operator="equal", (a, b) => a == b, Belt.Array.length(rels), 1)
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("readRelationships: FK name is FK_<child>_<parent>", cb => {
  let fakeRows: array<dict<JSON.t>> = [
    dict{
      "szObject": JSON.String("Orders"),
      "szColumn": JSON.String("CustomerID"),
      "szReferencedObject": JSON.String("Customers"),
      "szReferencedColumn": JSON.String("ID"),
    },
  ]
  ignore(readRelationships(~query=makeFakeQuery(fakeRows))
    ->Promise.then(result => {
      switch result {
      | Ok(rels) => {
          switch Belt.Array.get(rels, 0) {
          | Some(rel) => {
              assertion(~operator="equal", (a, b) => a == b, rel.name, "FK_Orders_Customers")
              assertion(~operator="equal", (a, b) => a == b, rel.table, "Orders")
              assertion(~operator="equal", (a, b) => a == b, rel.foreignTable, "Customers")
            }
          | None => assertion(~operator="equal", (a, b) => a == b, false, true)
          }
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=3, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("readRelationships: multi-column FK merges rows into one RelationshipInfo", cb => {
  let fakeRows: array<dict<JSON.t>> = [
    dict{
      "szObject": JSON.String("OrderLines"),
      "szColumn": JSON.String("OrderID"),
      "szReferencedObject": JSON.String("Orders"),
      "szReferencedColumn": JSON.String("ID"),
    },
    dict{
      "szObject": JSON.String("OrderLines"),
      "szColumn": JSON.String("ProductID"),
      "szReferencedObject": JSON.String("Orders"),
      "szReferencedColumn": JSON.String("ID"),
    },
  ]
  ignore(readRelationships(~query=makeFakeQuery(fakeRows))
    ->Promise.then(result => {
      switch result {
      | Ok(rels) => {
          assertion(~operator="equal", (a, b) => a == b, Belt.Array.length(rels), 1)
          switch Belt.Array.get(rels, 0) {
          | Some(rel) => {
              assertion(~operator="equal", (a, b) => a == b, rel.columns, ["OrderID", "ProductID"])
              assertion(~operator="equal", (a, b) => a == b, rel.foreignColumns, ["ID", "ID"])
            }
          | None => assertion(~operator="equal", (a, b) => a == b, false, true)
          }
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=3, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("readRelationships: results sorted by name (deterministic)", cb => {
  let fakeRows: array<dict<JSON.t>> = [
    dict{
      "szObject": JSON.String("Products"),
      "szColumn": JSON.String("CatID"),
      "szReferencedObject": JSON.String("Categories"),
      "szReferencedColumn": JSON.String("ID"),
    },
    dict{
      "szObject": JSON.String("Orders"),
      "szColumn": JSON.String("CustomerID"),
      "szReferencedObject": JSON.String("Customers"),
      "szReferencedColumn": JSON.String("ID"),
    },
  ]
  ignore(readRelationships(~query=makeFakeQuery(fakeRows))
    ->Promise.then(result => {
      switch result {
      | Ok(rels) => {
          switch (Belt.Array.get(rels, 0), Belt.Array.get(rels, 1)) {
          | (Some(r0), Some(r1)) => {
              // FK names: FK_<szObject>_<szReferencedObject>
              // "FK_Products_Categories" < "FK_Orders_Customers" alphabetically
              assertion(~operator="equal", (a, b) => a == b, r0.name, "FK_Products_Categories")
              assertion(~operator="equal", (a, b) => a == b, r1.name, "FK_Orders_Customers")
            }
          | _ => assertion(~operator="equal", (a, b) => a == b, false, true)
          }
        }
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=2, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("readRelationships: empty rows returns empty array Ok([])", cb => {
  ignore(readRelationships(~query=makeFakeQuery([]))
    ->Promise.then(result => {
      switch result {
      | Ok(rels) => assertion(~operator="equal", (a, b) => a == b, rels, [])
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})

testAsync("readRelationships: query error degrades to Ok([])", cb => {
  let fakeQuery = (~sql: string) => {
    Promise.resolve(Error(Errors.databaseError("Permission denied: cannot read MSysRelationships")))
  }
  ignore(readRelationships(~query=fakeQuery)
    ->Promise.then(result => {
      switch result {
      | Ok(rels) => assertion(~operator="equal", (a, b) => a == b, rels, [])
      | Error(_) => assertion(~operator="equal", (a, b) => a == b, false, true)
      }
      Promise.resolve()
    })
    ->Promise.then(() => {
      cb(~planned=1, ())
      Promise.resolve()
    })
    ->Promise.catch(e => {
      assertion(~operator="equal", (a, b) => a == b, false, true)
      cb(~planned=1, ())
      Promise.resolve()
    }))
})
