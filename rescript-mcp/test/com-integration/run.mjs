import winax from "winax";

const databasePath = process.env.ACCESS_TEST_DB;

if (process.platform !== "win32" || !databasePath) {
  console.log("COM integration skipped: Windows and ACCESS_TEST_DB are required");
  process.exit(0);
}

let app;
try {
  app = new winax.Object("Access.Application");
  app.Visible = false;
  app.OpenCurrentDatabase(databasePath);

  const now = app.Eval("Now()");
  if (now == null || String(now).length === 0) {
    throw new Error("Access Eval('Now()') returned an empty value");
  }

  console.log("COM integration passed: Access.Application opened the fixture and evaluated Now()");
} finally {
  try {
    app?.CloseCurrentDatabase();
  } catch {}
  try {
    app?.Quit();
  } catch {}
}
