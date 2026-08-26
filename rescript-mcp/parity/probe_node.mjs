// Supplementary probe — proves the connection-string fix that run.mjs needs
// Uses Driver={...};DBQ=<path>; pattern that matches Python OdbcAdapter.
import odbc from "odbc";

const dbq = process.env.ACCESS_TEST_DB;
if (!dbq) {
  console.error("ACCESS_TEST_DB not set");
  process.exit(1);
}

const connStr = `Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=${dbq};`;
let conn;
try {
  conn = await odbc.connect(connStr);
  console.log(`CONNECT OK: ${connStr}`);

  // Probe 1: Customers (user table) — confirms driver fully functional
  const r1 = await conn.query("SELECT COUNT(*) AS n FROM Customers", []);
  console.log(`Customers COUNT: ${JSON.stringify(r1)}`);

  // Probe 2: Customers schema
  const r2 = await conn.query("SELECT * FROM Customers WHERE 1=0", []);
  const cols = (r2.columns ?? []).map((c) => c.name);
  console.log(`Customers COLUMNS: ${JSON.stringify(cols)}`);

  // Probe 3: Orders + Products presence
  const r3 = await conn.query("SELECT COUNT(*) AS n FROM Orders", []);
  console.log(`Orders COUNT: ${JSON.stringify(r3)}`);
  const r4 = await conn.query("SELECT COUNT(*) AS n FROM Products", []);
  console.log(`Products COUNT: ${JSON.stringify(r4)}`);

  // Probe 4: MSysObjects ACL check
  try {
    await conn.query("SELECT COUNT(*) FROM MSysObjects", []);
    console.log("MSysObjects: accessible");
  } catch (e) {
    console.log(`MSysObjects: DENIED (${e.message ?? e})`);
  }

  // Probe 5: INFORMATION_SCHEMA absence (Access ODBC doesn't expose it)
  try {
    await conn.query("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES", []);
    console.log("INFORMATION_SCHEMA.TABLES: accessible");
  } catch (e) {
    console.log(`INFORMATION_SCHEMA.TABLES: ${e.message ?? e}`);
  }

  await conn.close();
  console.log("CLOSE OK");
  process.exit(0);
} catch (e) {
  console.error(`FATAL: ${e.message ?? e}`);
  if (conn) {
    try { await conn.close(); } catch {}
  }
  process.exit(1);
}