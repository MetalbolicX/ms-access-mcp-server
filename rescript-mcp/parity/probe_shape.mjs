// Probe: what shape does conn.query() return?
import odbc from "odbc";

const dbq = process.env.ACCESS_TEST_DB;
const conn = await odbc.connect(
  `Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=${dbq};`
);

// Try a SELECT COUNT
const r1 = await conn.query("SELECT COUNT(*) AS n FROM Customers", []);
console.log("r1 type:", typeof r1, "isArray:", Array.isArray(r1));
console.log("r1 keys:", r1 === null ? "null" : Object.keys(r1));
console.log("r1.rows:", JSON.stringify(r1.rows ?? null));
console.log("r1.count:", r1.count);
console.log("r1.columns:", JSON.stringify(r1.columns ?? null));
console.log("r1[0]:", JSON.stringify(r1[0] ?? null));

// Try a SELECT with no alias
const r2 = await conn.query("SELECT COUNT(*) FROM Customers", []);
console.log("\nr2 type:", typeof r2, "isArray:", Array.isArray(r2));
console.log("r2.count:", r2.count);

// Try a SELECT with literal value
const r3 = await conn.query("SELECT * FROM Customers WHERE 1=0", []);
console.log("\nr3 (empty result) keys:", r3 === null ? "null" : Object.keys(r3));
console.log("r3.rows:", JSON.stringify(r3.rows ?? null));

await conn.close();
