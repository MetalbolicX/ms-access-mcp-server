// run.mjs — orchestrator for the differential parity harness.
//
// Iterates cases/parity/cases/*.json, runs the ReScript and Python
// children against per-side copies of the fixture for mutating cases,
// normalizes, differs, and prints a summary. Exits non-zero on any
// mismatch so the harness can gate CI.
//
// Env vars (binding per plan 018 amendment 4):
//   ACCESS_TEST_DB              — absolute path to fixture .accdb
//   ACCESS_MCP_ALLOWED_DIRS     — semicolon-separated (fixture + temp export)
//   ACCESS_MCP_READONLY=false   — disable read-only mode on the ReScript side
//   ACCESS_TEST_ASSUME_ACE=1    — assert ACE ODBC driver available
//
// All four MUST be set; the runner refuses to start otherwise.
//
// On Windows + ACCESS_TEST_ASSUME_ACE=1: full suite, exits 1 on mismatch.
// Off-Windows or without ACE driver: skip cleanly with exit 0.

import { copyFileSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { normalize, diff } from "./normalize.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, "..", "..");
const REPO_FIXTURE = join(REPO_ROOT, "tests", "integration", "fixtures", "test_db.accdb");
const PYTHON = join(REPO_ROOT, ".venv", "Scripts", "python.exe");
const PYTHON_DRIVER = join(__dirname, "..", "scripts", "parity_driver.py");
const NODE = process.execPath;
const RS_RUNNER = join(__dirname, "runRescript.mjs");
const CASES_DIR = join(__dirname, "cases");

// ---------------------------------------------------------------------------
// Gate: platform + driver + env vars
// ---------------------------------------------------------------------------

if (process.platform !== "win32") {
  console.log("parity: skipped (non-Windows platform; ODBC driver not portable)");
  process.exit(0);
}

if (process.env.ACCESS_TEST_ASSUME_ACE !== "1") {
  console.log("parity: skipped (ACCESS_TEST_ASSUME_ACE!=1)");
  process.exit(0);
}

const fixture = process.env.ACCESS_TEST_DB ?? REPO_FIXTURE;
if (!existsSync(fixture)) {
  console.log(`parity: skipped (fixture not found at ${fixture})`);
  process.exit(0);
}

// Per plan 018 amendment 4: pin env for BOTH child processes.
// The runner owns the env contract; children must not have to set it.
// The allowed dirs include the fixture directory, the system temp (where
// per-side copies land for mutating cases), and the explicit
// ACCESS_MCP_ALLOWED_DIRS if the user provided one. Without this, the
// ReScript facade's PathGuard rejects the per-side temp copies as
// "path not allowed".
const pinnedEnv = {
  ...process.env,
  ACCESS_TEST_DB: fixture,
  ACCESS_MCP_ALLOWED_DIRS: [
    dirname(fixture),
    tmpdir(),
    process.env.ACCESS_MCP_ALLOWED_DIRS ?? "",
  ]
    .filter((s) => s.length > 0)
    .join(";"),
  ACCESS_MCP_READONLY: "false",
  ACCESS_TEST_ASSUME_CE: "1",
};

// ---------------------------------------------------------------------------
// Per-case driver invocation
// ---------------------------------------------------------------------------

/**
 * Run a child process against a specific fixture copy. Returns the parsed
 * envelope JSON or { error } on driver failure.
 */
function runChild(childPath, args, env, label) {
  const result = spawnSync(childPath, args, {
    env,
    encoding: "utf8",
    timeout: 60_000,
  });
  if (result.status !== 0) {
    return {
      error: `${label} exit ${result.status}`,
      stderr: (result.stderr ?? "").slice(0, 2000),
      stdout: result.stdout ?? "",
    };
  }
  const text = (result.stdout ?? "").trim();
  if (!text) {
    return { error: `${label} produced no output`, stderr: (result.stderr ?? "").slice(0, 1000) };
  }
  try {
    return JSON.parse(text);
  } catch (e) {
    return { error: `${label} produced invalid JSON: ${e.message}`, stdout: text.slice(0, 2000) };
  }
}

/**
 * Run the Python driver against a specific fixture copy. The driver
 * reads ACCESS_TEST_DB internally.
 */
function runPython(childFixturePath, caseJson) {
  const env = { ...pinnedEnv, ACCESS_TEST_DB: childFixturePath, PARITY_EXPORT_DIR: tmpdir() };
  return runChild(PYTHON, [PYTHON_DRIVER, caseJson], env, "python");
}

/**
 * Run the ReScript runner against a specific fixture copy. The runner
 * reads ACCESS_TEST_DB internally.
 */
function runRescript(childFixturePath, caseJson) {
  const env = { ...pinnedEnv, ACCESS_TEST_DB: childFixturePath, PARITY_EXPORT_DIR: tmpdir() };
  return runChild(NODE, [RS_RUNNER, caseJson], env, "rescript");
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const caseFiles = readdirSync(CASES_DIR)
  .filter((f) => f.endsWith(".json"))
  .sort();

let passed = 0;
let mismatched = 0;
let errored = 0;
const findings = [];

// Per-side scratch dir for fixture copies (mutating cases only).
// We create it BEFORE we set pinnedEnv so its absolute path lands in the
// allowed-dirs list (per-side copy paths must be PathGuard-allowed).
const scratchRoot = mkdtempSync(join(tmpdir(), "parity-007-"));
pinnedEnv.ACCESS_MCP_ALLOWED_DIRS = [
  pinnedEnv.ACCESS_MCP_ALLOWED_DIRS,
  scratchRoot,
]
  .filter((s) => s.length > 0)
  .join(";");

for (const caseFile of caseFiles) {
  const casePath = join(CASES_DIR, caseFile);
  const caseObj = JSON.parse(readFileSync(casePath, "utf8"));

  const mutating = caseObj.mutating === true;
  const needsConnect = caseObj.operation !== "connect_access";

  // Allocate per-side fixture copies for mutating cases. For non-
  // mutating cases that need a connect, both sides share the pristine
  // fixture (per amendment 3).
  let pyFixture = fixture;
  let rsFixture = fixture;
  if (mutating) {
    const caseScratch = join(scratchRoot, caseFile.replace(/\.json$/, ""));
    mkdirSync(caseScratch, { recursive: true });
    pyFixture = join(caseScratch, "py.accdb");
    rsFixture = join(caseScratch, "rs.accdb");
    copyFileSync(fixture, pyFixture);
    copyFileSync(fixture, rsFixture);
  }

  // For lifecycle ops that need an existing connection (e.g. set_active),
  // prime both pools with a connect first. The Python side's MCP
  // container is module-scoped, so a connect here persists for the
  // duration of the child process.
  if (needsConnect && caseObj.operation !== "is_connected" && caseObj.operation !== "list_connections") {
    runChild(
      PYTHON,
      [PYTHON_DRIVER, JSON.stringify({ operation: "connect_access", args: {} })],
      { ...pinnedEnv, ACCESS_TEST_DB: pyFixture, PARITY_EXPORT_DIR: tmpdir() },
      "python-prime",
    );
  }

  const pyResult = runPython(pyFixture, casePath);
  const rsResult = runRescript(rsFixture, casePath);

  // Driver-level errors (non-zero exit, bad JSON) are reported as
  // mismatches with a "DRIVER" prefix; they're actionable.
  if (pyResult.error || rsResult.error) {
    errored++;
    findings.push({
      operation: caseObj.operation,
      case: caseFile,
      diff: {
        path: "DRIVER",
        expected: pyResult.error ? null : "ok",
        actual: rsResult.error ? `rescript: ${rsResult.error}` : `python: ${pyResult.error}`,
      },
      stderr: pyResult.stderr ?? rsResult.stderr,
    });
    console.log(`  ERROR  ${caseFile} — driver failure`);
    continue;
  }

  const volatile = caseObj.volatileFields ?? [];
  const pyN = normalize(pyResult, volatile);
  const rsN = normalize(rsResult, volatile);

  const d = diff(pyN, rsN);
  if (d === null) {
    passed++;
    console.log(`  PASS  ${caseFile}`);
  } else {
    mismatched++;
    findings.push({
      operation: caseObj.operation,
      case: caseFile,
      diff: d,
    });
    console.log(`  FAIL  ${caseFile} — diff at ${d.path}`);
  }
}

// Cleanup scratch dir
try {
  rmSync(scratchRoot, { recursive: true, force: true });
} catch {
  // ignore
}

console.log("");
console.log(`parity: ${caseFiles.length} cases, ${passed} matched, ${mismatched} mismatched, ${errored} errored`);

// Persist findings for step 6 review.
const findingsPath = join(__dirname, "findings.json");
writeFileSync(findingsPath, JSON.stringify(findings, null, 2));

if (mismatched > 0 || errored > 0) {
  process.exit(1);
}
process.exit(0);