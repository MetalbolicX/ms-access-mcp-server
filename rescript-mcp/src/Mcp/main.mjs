// main.mjs — executable entrypoint for the MCP stdio server.
//
// Server.res.mjs is a library module (tests import it and would otherwise
// open a stdio listener on import). This shim is the only place that
// invokes run(), keeping imports side-effect free. Logs go to stderr;
// stdout is reserved for the MCP JSON-RPC protocol channel.
import { run } from "./Server.res.mjs";

run().catch((err) => {
  console.error("[ms-access-mcp] fatal:", err?.message ?? err);
  if (err?.stack) console.error(err.stack);
  process.exit(1);
});
