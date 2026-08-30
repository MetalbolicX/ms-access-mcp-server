import { spawn } from "child_process";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const rescriptMcpRoot = join(__dirname, "..", "..");
const workspaceRoot = join(rescriptMcpRoot, "..");
const testDb = join(workspaceRoot, "db", "northwind.accdb");
const allowedDirs = join(workspaceRoot, "db");

const mainMjs = join(rescriptMcpRoot, "src", "Mcp", "main.mjs");

const runSmokeTest = async () => {
  const proc = spawn("node", [mainMjs], {
    cwd: rescriptMcpRoot,
    stdio: ["pipe", "pipe", "pipe"],
    env: {
      ...process.env,
      ACCESS_MCP_READONLY: "true",
      ACCESS_TEST_DB: testDb,
      ACCESS_MCP_ALLOWED_DIRS: allowedDirs,
    },
  });

  let stdout = "";
  let id = 1;
  const pending = new Map();

  proc.stdout.on("data", (chunk) => {
    stdout += chunk.toString();
    const lines = stdout.split("\n");
    stdout = lines.pop() || "";
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const msg = JSON.parse(line);
        const resolve = pending.get(msg.id);
        if (resolve) {
          resolve(msg);
          pending.delete(msg.id);
        }
      } catch {
        // ignore parse errors
      }
    }
  });

  proc.stderr.on("data", (chunk) => {
    const text = chunk.toString().trim();
    if (text && !text.includes("ms-access-mcp")) {
      console.error("[server]", text);
    }
  });

  const send = (method, params = {}, timeoutMs = 5000) => {
    const msgId = id++;
    const msg = { jsonrpc: "2.0", id: msgId, method, params };
    const str = JSON.stringify(msg);
    proc.stdin.write(str + "\n");
    return new Promise((resolve) => {
      pending.set(msgId, resolve);
      setTimeout(() => {
        if (pending.has(msgId)) {
          pending.delete(msgId);
          resolve({ jsonrpc: "2.0", id: msgId, result: null, _timeout: true });
        }
      }, timeoutMs);
    });
  }

  await new Promise((r) => setTimeout(r, 2000));

  const initResult = await send("initialize", {
    protocolVersion: "2024-11-05",
    capabilities: {},
    clientInfo: { name: "northwind-stdio-test", version: "1.0.0" },
  });
  if (initResult._timeout || !initResult.result) {
    throw new Error("Server did not respond to initialize");
  }

  proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized", params: {} }) + "\n");
  await new Promise((r) => setTimeout(r, 500));

  const listConn = await send("tools/call", { name: "list_connections", arguments: {} });
  if (listConn._timeout) throw new Error("list_connections timed out");

  const backslashDb = testDb.replace(/\//g, "\\");
  const connectResult = await send("tools/call", {
    name: "connect_access",
    arguments: { database_path: backslashDb, name: "northwind", backend: "odbc" },
  });
  if (connectResult._timeout) throw new Error("connect_access timed out");
  const connectText = JSON.stringify(connectResult.result?.content || "");
  if (connectResult.result?.isError) {
    throw new Error(`connect_access failed: ${connectText}`);
  }

  const tablesResult = await send("tools/call", {
    name: "get_tables",
    arguments: { connection_name: "northwind" },
  });
  if (tablesResult._timeout) throw new Error("get_tables timed out");
  if (tablesResult.result?.isError) {
    throw new Error(`get_tables failed: ${JSON.stringify(tablesResult.result?.content)}`);
  }

  const tablesContent = JSON.parse(tablesResult.result?.content?.[0]?.text || "{}");
  if (!tablesContent.success) {
    throw new Error(`get_tables returned error: ${JSON.stringify(tablesContent)}`);
  }
  const tableNames = tablesContent.tables.map((t) => t.name).sort();
  const expected = ["Categories", "Customers", "Employees", "OrderDetails", "Orders", "Products", "Shippers", "Suppliers"];
  for (const name of expected) {
    if (!tableNames.includes(name)) {
      throw new Error(`Missing expected table: ${name}`);
    }
  }

  proc.kill();
  console.log("Northwind stdio smoke PASSED");
}

runSmokeTest().catch((err) => {
  console.error("[smoke] FAILED:", err.message);
  process.exit(1);
});
