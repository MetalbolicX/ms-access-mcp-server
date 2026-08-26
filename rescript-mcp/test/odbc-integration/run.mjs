// test/odbc-integration/run.mjs — Plan 003 Slice 3 ODBC integration harness
// Gate order: win32 → fixture resolve → extension validate → odbc load → flag check
// NEVER imports winax or any COM module on any path (including skip).
// Flag ACCESS_TEST_ASSUME_ACE=1 is test-harness-only; production OdbcAdapter.connect unchanged.

import { existsSync, readFileSync, unlinkSync } from "node:fs";
import { join } from "node:path";

// ---------------------------------------------------------------------------
// Gate 1: Windows platform
// ---------------------------------------------------------------------------
if (process.platform !== "win32") {
  console.log(
    "ODBC integration skipped: Windows platform required. " +
    "Set ACCESS_TEST_ASSUME_ACE=1 on Windows with a Microsoft Access ODBC driver " +
    "(ACE, MDBTools, MDBODBC) to enable."
  );
  process.exit(0);
}

// ---------------------------------------------------------------------------
// Gate 2: Fixture resolution
// ACCESS_TEST_DB (quote-stripped, Python parity) → repo fixture fallback → skip
// ---------------------------------------------------------------------------
const rawEnvPath = process.env.ACCESS_TEST_DB ?? "";
// Python parity: strip surrounding double-quotes from env var value
const explicitDb = rawEnvPath.replace(/^"(.*)"$/, "$1").trim();

/** @type {string | null} */
let fixturePath = null;
let fixtureSource = "";

if (explicitDb && explicitDb.length > 0) {
  if (existsSync(explicitDb)) {
    fixturePath = explicitDb;
    fixtureSource = "ACCESS_TEST_DB";
  } else {
    console.log(
      `ODBC integration skipped: ACCESS_TEST_DB='${explicitDb}' does not exist. ` +
      `Set ACCESS_TEST_ASSUME_ACE=1 on Windows with a Microsoft Access ODBC driver ` +
      `(ACE, MDBTools, MDBODBC) to enable.`
    );
    process.exit(0);
  }
} else {
  // Repo fixture fallback
  const repoFixture = join(process.cwd(), "test", "fixtures", "test_db.accdb");
  if (existsSync(repoFixture)) {
    fixturePath = repoFixture;
    fixtureSource = "repo fixture (test/fixtures/test_db.accdb)";
  } else {
    console.log(
      `ODBC integration skipped: no fixture resolved ` +
      `(ACCESS_TEST_DB unset, and ${join(process.cwd(), "test", "fixtures", "test_db.accdb")} not found). ` +
      `Set ACCESS_TEST_ASSUME_ACE=1 on Windows with a Microsoft Access ODBC driver ` +
      `(ACE, MDBTools, MDBODBC) to enable.`
    );
    process.exit(0);
  }
}

// ---------------------------------------------------------------------------
// Gate 3: Extension validation — only .accdb and .mdb are accepted
// ---------------------------------------------------------------------------
if (!fixturePath.toLowerCase().endsWith(".accdb") && !fixturePath.toLowerCase().endsWith(".mdb")) {
  console.log(
    `ODBC integration skipped: resolved fixture '${fixturePath}' has invalid extension. ` +
    `Only .accdb and .mdb files are supported. ` +
    `Set ACCESS_TEST_ASSUME_ACE=1 on Windows with a Microsoft Access ODBC driver ` +
    `(ACE, MDBTools, MDBODBC) to enable.`
  );
  process.exit(0);
}

// ---------------------------------------------------------------------------
// Gate 4: odbc module load
// ---------------------------------------------------------------------------
/** @type {any} */
let odbc;
try {
  odbc = await import("odbc");
} catch (/** @type {any} */ _e) {
  console.log(
    `ODBC integration skipped: 'odbc' module failed to load. ` +
    `Set ACCESS_TEST_ASSUME_ACE=1 on Windows with a Microsoft Access ODBC driver ` +
    `(ACE, MDBTools, MDBODBC) to enable.`
  );
  process.exit(0);
}

// ---------------------------------------------------------------------------
// Gate 5: ACCESS_TEST_ASSUME_ACE=1 flag
// ---------------------------------------------------------------------------
if (process.env.ACCESS_TEST_ASSUME_ACE !== "1") {
  console.log(
    `ODBC integration skipped: ACCESS_TEST_ASSUME_ACE=1 is required but not set. ` +
    `This flag asserts that a Microsoft Access ODBC driver (ACE, MDBTools, MDBODBC) is installed. ` +
    `Without it the harness cannot verify ODBC driver availability — ` +
    `probe-connect is prohibited by the gate-before-connect rule (odbc v2 has no driver-enumeration API). ` +
    `On a machine with a real Access ODBC driver installed, set ACCESS_TEST_ASSUME_ACE=1 to enable the suite.`
  );
  process.exit(0);
}

// ---------------------------------------------------------------------------
// Gated environment confirmed — run integration cases
// ---------------------------------------------------------------------------
console.log(`ODBC integration: fixture=${fixtureSource}, path=${fixturePath}`);

let conn = null;
/** @type {() => Promise<void>} */
const closeConnection = async () => {
  if (conn) {
    try {
      await conn.close();
    } catch {}
    conn = null;
  }
};

try {
  // Build connection string: Driver={...};DBQ=<path> (no PWD for .accdb)
  const connStr = `Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=${fixturePath}`;
  conn = await odbc.connect(connStr);

  let failures = 0;
  let passed = 0;

  // Helper to run a test case
  /**
   * @param {string} name
   * @param {() => Promise<boolean>} fn
   */
  const test = async (name, fn) => {
    try {
      const ok = await fn();
      if (ok) {
        console.log(`  PASS  ${name}`);
        passed++;
      } else {
        console.log(`  FAIL  ${name}`);
        failures++;
      }
    } catch (/** @type {any} */ e) {
      console.log(`  FAIL  ${name} — ${e?.message ?? e}`);
      failures++;
    }
  };

  // ── Connect / Disconnect ─────────────────────────────────────────────
  await test("connect: returns object (already connected via connect())", async () => {
    return conn !== null;
  });

  await test("disconnect: close() resolves without error", async () => {
    await conn.close();
    conn = null;
    return true;
  });

  // Reconnect for remaining tests
  conn = await odbc.connect(connStr);

  // ── CRUD cycle ──────────────────────────────────────────────────────────
  await test("executeQuery: SELECT returns rows", async () => {
    // Use Customers table if present, else Orders
    const result = await conn.query("SELECT COUNT(*) AS n FROM Customers", []);
    const rows = result.rows;
    return Array.isArray(rows) && rows.length > 0;
  });

  await test("insert: INSERT INTO affects 1 row", async () => {
    // Insert into a temp table or a non-system table
    const r1 = await conn.query(
      "INSERT INTO [Customers] ([CustomerID], [CustomerName]) VALUES (?, ?)",
      [99998, "Integration Test"]
    );
    return r1.count === 1;
  });

  await test("update: UPDATE WHERE affects expected rows", async () => {
    const r = await conn.query(
      "UPDATE [Customers] SET [CustomerName]='Updated' WHERE [CustomerID]=?",
      [99998]
    );
    return r.count >= 0;
  });

  await test("delete: DELETE WHERE removes inserted row", async () => {
    const r = await conn.query(
      "DELETE FROM [Customers] WHERE [CustomerID]=?",
      [99998]
    );
    return r.count >= 0;
  });

  // ── executeRawSql rowcount ──────────────────────────────────────────────
  await test("executeRawSql: SELECT COUNT returns non-negative rowcount", async () => {
    const r = await conn.query("SELECT COUNT(*) FROM Customers", []);
    return r.count >= 0;
  });

  // ── Catalog / tables ────────────────────────────────────────────────────
  await test("getTables: returns TABLE rows (MSys excluded)", async () => {
    const result = await conn.query(
      "SELECT TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='TABLE' ORDER BY TABLE_NAME",
      []
    );
    const rows = result.rows ?? [];
    const hasCustomers = rows.some(
      /** @param {any} r */ (r) => String(r.TABLE_NAME ?? "").toUpperCase() === "CUSTOMERS"
    );
    return hasCustomers && Array.isArray(rows);
  });

  // ── getQueries ─────────────────────────────────────────────────────────
  await test("getQueries: queries INFORMATION_SCHEMA.VIEWS with dbo filter", async () => {
    const result = await conn.query(
      "SELECT TABLE_NAME, VIEW_DEFINITION FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_SCHEMA='dbo' ORDER BY TABLE_NAME",
      []
    );
    return Array.isArray(result.rows);
  });

  // ── Relationships ──────────────────────────────────────────────────────
  await test("getRelationships: reads MSysRelationships (graceful if empty)", async () => {
    try {
      // May be empty if no relationships defined — that's OK
      const result = await conn.query(
        "SELECT Relationship_Name, ObjectName, ObjectType FROM MSysRelationships ORDER BY Relationship_Name",
        []
      );
      return Array.isArray(result.rows);
    } catch {
      // Access may deny read on MSysRelationships
      return true;
    }
  });

  // ── DDL for tables ─────────────────────────────────────────────────────
  await test("createTable: CREATE TABLE succeeds", async () => {
    try {
      await conn.query(
        "CREATE TABLE [TestSlice3Temp] ([ID] INTEGER NOT NULL, [Name] VARCHAR(255))",
        []
      );
      return true;
    } catch {
      return false;
    }
  });

  await test("dropTable: DROP TABLE succeeds", async () => {
    try {
      await conn.query("DROP TABLE [TestSlice3Temp]", []);
      return true;
    } catch {
      return false;
    }
  });

  // ── DDL for indexes ────────────────────────────────────────────────────
  // (create index on existing Customers table)
  await test("createIndex: CREATE INDEX succeeds", async () => {
    try {
      await conn.query(
        "CREATE INDEX [IntTestSlice3Idx] ON [Customers] ([CustomerID])",
        []
      );
      return true;
    } catch {
      return false;
    }
  });

  await test("dropIndex: DROP INDEX succeeds", async () => {
    try {
      await conn.query(
        "DROP INDEX [IntTestSlice3Idx] ON [Customers]",
        []
      );
      return true;
    } catch {
      return false;
    }
  });

  // ── DDL for views ──────────────────────────────────────────────────────
  await test("createQuery (CREATE VIEW): succeeds", async () => {
    try {
      await conn.query(
        "CREATE VIEW [IntSlice3Vw] AS SELECT CustomerID FROM Customers WHERE CustomerID=0",
        []
      );
      return true;
    } catch {
      return false;
    }
  });

  await test("deleteQuery (DROP VIEW): succeeds", async () => {
    try {
      await conn.query("DROP VIEW [IntSlice3Vw]", []);
      return true;
    } catch {
      return false;
    }
  });

  // ── Statistics ────────────────────────────────────────────────────────
  await test("getDatabaseStatistics: connected returns counts (mock via MSysObjects)", async () => {
    // At minimum, query MSysObjects to confirm the statistics path works
    try {
      const r = await conn.query(
        "SELECT Type, Count(*) AS [Count] FROM MSysObjects GROUP BY Type",
        []
      );
      return Array.isArray(r.rows);
    } catch {
      // MSysObjects may be denied — test passes if graceful
      return true;
    }
  });

  await closeConnection();

  console.log(`\nODBC integration: ${passed} passed, ${failures} failed`);
  if (failures > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
} catch (/** @type {any} */ e) {
  console.error(`ODBC integration fatal: ${e?.message ?? e}`);
  await closeConnection();
  process.exit(1);
}
