// run.ts — orchestrator for the differential parity harness.
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
//   ACCESS_TEST_ASSUME_ACE=1   — assert ACE ODBC driver available
//   PARITY_SOURCE_DB            — absolute path to linked-table source .accdb
//
// All four MUST be set; the runner refuses to start otherwise.
//
// On Windows + ACCESS_TEST_ASSUME_ACE=1: full suite, exits 1 on mismatch.
// Off-Windows or without ACE driver: skip cleanly with exit 0.
//
// Exact-case selection:
//   --case <relative-path>  executes ONLY that case (relative to casesDir)
//
// Artifact persistence:
//   Every runner invocation persists an artifact under parity/runs/<run-id>/
//   containing paired envelopes, setup status, phase markers, and exit metadata.

import { copyFileSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { spawnSync, execSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import type { SpawnSyncReturns } from "node:child_process";
import { createHash } from "node:crypto";

import { normalize, diff } from "./normalize.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
// __dirname is parity/dist/ (one level deeper than parity/run.mjs), so three levels up
const REPO_ROOT = resolve(__dirname, "..", "..", "..");
const REPO_FIXTURE = join(REPO_ROOT, "tests", "integration", "fixtures", "test_db.accdb");
const PYTHON = join(REPO_ROOT, ".venv", "Scripts", "python.exe");
const PYTHON_DRIVER = join(__dirname, "..", "..", "scripts", "parity_driver.py");
const NODE = process.execPath;
const RS_RUNNER_JS = join(__dirname, "runRescript.js");
// cases/ is at parity/cases, one level up from parity/dist/
const DEFAULT_CASES_DIR = join(__dirname, "..", "cases");

// ---------------------------------------------------------------------------
// CLI argument parsing
// ---------------------------------------------------------------------------

function parseArgs(argv: string[]): { casesDir: string; requireReadOnly: boolean; exactCase: string | null } {
  let casesDir = DEFAULT_CASES_DIR;
  let requireReadOnly = false;
  let exactCase: string | null = null;

  for (const arg of argv.slice(2)) {
    if (arg.startsWith("--cases-dir=")) {
      casesDir = resolve(REPO_ROOT, arg.slice("--cases-dir=".length));
    } else if (arg === "--require-read-only") {
      requireReadOnly = true;
    } else if (arg.startsWith("--case=")) {
      exactCase = arg.slice("--case=".length);
    }
  }

  return { casesDir, requireReadOnly, exactCase };
}

const { casesDir, requireReadOnly, exactCase } = parseArgs(process.argv);

/** Case file shape (matches cases.schema.json) */
interface CaseFile {
  operation: string;
  args?: Record<string, unknown>;
  mutating?: boolean;
  volatileFields?: string[];
  variant?: string;
  setup?: Array<{ operation: string; args: Record<string, unknown> }>;
  skip?: boolean;
  skipReason?: string;
}

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

// COM variant: skip if winax is not available on this platform
if (process.env.PARITY_VARIANT === "com") {
  const hasWinax = (() => {
    try {
      require("winax");
      return true;
    } catch {
      return false;
    }
  })();
  if (!hasWinax) {
    console.log("parity: skipped (PARITY_VARIANT=com but winax not available)");
    process.exit(0);
  }
  if (process.platform !== "win32") {
    console.log("parity: skipped (PARITY_VARIANT=com requires Windows)");
    process.exit(0);
  }
}

// Per plan 018 amendment 4: pin env for BOTH child processes.
// The runner owns the env contract; children must not have to set it.
// The allowed dirs include the fixture directory, the system temp (where
// per-side copies land for mutating cases), and the explicit
// ACCESS_MCP_ALLOWED_DIRS if the user provided one. Without this, the
// ReScript facade's PathGuard rejects the per-side temp copies as
// "path not allowed".
// PARITY_SOURCE_DB — path to the linked-table source fixture
const PARITY_SOURCE_DB = join(REPO_ROOT, "db", "postgres.accdb");
if (!existsSync(PARITY_SOURCE_DB)) {
  console.error(`parity: PARITY_SOURCE_DB not found at ${PARITY_SOURCE_DB}`);
  process.exit(1);
}

const pinnedEnv: Record<string, string> = {
  ...process.env,
  ACCESS_MCP_ALLOWED_DIRS: [
    dirname(fixture),
    tmpdir(),
    process.env.ACCESS_MCP_ALLOWED_DIRS ?? "",
  ]
    .filter((s) => s.length > 0)
    .join(";"),
  ACCESS_MCP_READONLY: "false",
  ACCESS_TEST_ASSUME_CE: "1",
  PARITY_SOURCE_DB,
};
// ACCESS_TEST_DB must be set AFTER ...process.env to override any inherited value
pinnedEnv.ACCESS_TEST_DB = fixture;

// ---------------------------------------------------------------------------
// Run-ID and artifact persistence
// ---------------------------------------------------------------------------

const RUN_ID = `run-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
const RUN_ARTIFACT_DIR = join(__dirname, "..", "runs", RUN_ID);

function persistArtifact(basename: string, content: string): void {
  try {
    mkdirSync(RUN_ARTIFACT_DIR, { recursive: true });
    writeFileSync(join(RUN_ARTIFACT_DIR, basename), content, "utf8");
  } catch {
    // Non-fatal: artifact persistence failure does not gate the run
  }
}

function redactedEnv(env: Record<string, string>): Record<string, string> {
  // Strip connection strings, passwords, and DB secrets from env before persisting
  const redaction = /password|connection|secret|key|token/i;
  const redacted: Record<string, string> = {};
  for (const [k, v] of Object.entries(env)) {
    redacted[k] = redaction.test(k) ? "[REDACTED]" : v;
  }
  return redacted;
}

/** Phase markers flow through the envelope WITHOUT polluting the case-result body. */
interface PhaseMarkers {
  setup?: string;
  nativeOp?: string;
  postcondition?: string;
  disconnect?: string;
  serialization?: string;
  processExit?: string;
}

interface RunArtifact {
  runId: string;
  timestamp: string;
  casesDir: string;
  exactCase: string | null;
  gitSha?: string;
  compiledArtifactPath?: string;
  phase: PhaseMarkers;
  pythonChild?: ChildStatus;
  rescriptChild?: ChildStatus;
  setupStatus?: string;
}

interface ChildStatus {
  statusCode: number | null;
  signal: string | null;
  timeout: boolean;
  spawnError: string | null;
  stdoutValidJson: boolean;
  stdoutShapeValid: boolean;
  envelopeBackend?: string;
  logicalEquality: boolean;
  skipReason: string | null;
  stderrRedacted: string;
  phase: PhaseMarkers;
}

function buildGitInfo(): { sha: string; artifactPath: string } | null {
  try {
    const sha = execSync("git rev-parse HEAD", { encoding: "utf8", shell: "cmd.exe" }).trim();
    const artifactPath = join(REPO_ROOT, "rescript-mcp", "src", "Services", "Facade.res.mjs");
    return { sha, artifactPath };
  } catch {
    return null;
  }
}

const gitInfo = buildGitInfo();

// ---------------------------------------------------------------------------
// Per-case driver invocation
// ---------------------------------------------------------------------------

interface DriverEnvelope {
  success: boolean;
  rows?: unknown[];
  count?: number;
  columns?: unknown[];
  error?: string | null;
  backend?: string; // "com" | "odbc" | "unavailable"
  [key: string]: unknown;
}

interface ChildStatusDetail {
  statusCode: number | null;
  signal: string | null;
  timeout: boolean;
  spawnError: string | null;
  stdoutValidJson: boolean;
  stdoutShapeValid: boolean;
  envelopeBackend: string | null;
  logicalEquality: boolean;
  skipReason: string | null;
  stderrRedacted: string;
  phase: PhaseMarkers;
}

interface DriverResult {
  ok: true;
  result: DriverEnvelope;
  stderr?: string;
  childStatus: ChildStatusDetail;
}

interface DriverError {
  ok: false;
  driverError: string;
  stderr?: string;
  stdout?: string;
  childStatus: ChildStatusDetail;
}

/** Shared empty phase marker object to avoid allocation on hot path */
const NO_PHASE: PhaseMarkers = {};

/**
 * Run a child process against a specific fixture copy. Returns a discriminated
 * result with full child-status recording.
 *
 * Records per child:
 *   - status code, signal, timeout/spawn error
 *   - stdout validity (parses as JSON / matches expected envelope shape)
 *   - logical result (equality with paired side — DIAGNOSTIC ONLY, never acceptance)
 *   - skip reason
 *
 * Nonzero exit or timeout remains an error even when JSON is valid.
 */
function runChild(
  childPath: string,
  args: string[],
  env: Record<string, string>,
  label: string,
): DriverResult | DriverError {
  const basePhase: PhaseMarkers = { nativeOp: `${label}-start` };

  const result: SpawnSyncReturns<string> = spawnSync(childPath, args, {
    env,
    encoding: "utf8",
    timeout: 60_000,
  });

  const text = (result.stdout ?? "").trim();
  const stderrRaw = (result.stderr ?? "").slice(0, 2000);
  const phase: PhaseMarkers = {
    ...basePhase,
    processExit: `exit-${result.status ?? "null"}`,
  };

  // Build childStatus shared between ok and error paths
  const childStatusBase: ChildStatusDetail = {
    statusCode: result.status,
    signal: result.signal ?? null,
    timeout: result.status === null && result.error !== undefined,
    spawnError: result.error?.message ?? null,
    stdoutValidJson: false,
    stdoutShapeValid: false,
    envelopeBackend: null,
    logicalEquality: false,
    skipReason: null,
    stderrRedacted: stderrRaw,
    phase,
  };

  // Plan 036 T4: tolerate non-zero exit IF the child wrote a valid envelope
  // to stdout before crashing. This accommodates the COM winax teardown
  // crash (033-F-001: "MultiIsolatePlatform::DisposeIsolate", exit 134)
  // which happens AFTER the ReScript child has already serialized the
  // result. The envelope is the contract; the exit code is secondary.
  // A genuine crash that prevents serialization (no stdout) still produces
  // driverError via the empty-output check below.
  //
  // IMPORTANT: even with valid JSON, nonzero exit is still recorded as an
  // error condition in childStatus — logical equality is DIAGNOSTIC ONLY.
  if (result.status !== 0) {
    phase.serialization = `${label}-nonzero-exit`;
    if (text) {
      try {
        const envelope = JSON.parse(text) as DriverEnvelope;
        childStatusBase.stdoutValidJson = true;
        childStatusBase.stdoutShapeValid = envelope !== null && typeof envelope === "object" && "success" in envelope;
        childStatusBase.envelopeBackend = envelope.backend ?? null;
        phase.serialization = `${label}-nonzero-with-valid-json`;
        return {
          ok: true,
          result: envelope,
          stderr: stderrRaw,
          childStatus: { ...childStatusBase, phase },
        };
      } catch {
        // stdout present but not valid JSON — fall through to driver error
        phase.serialization = `${label}-nonzero-invalid-json`;
      }
    }
    if (!text) {
      return {
        ok: false,
        driverError: `${label} exit ${result.status} (no output)`,
        stderr: stderrRaw,
        childStatus: { ...childStatusBase, phase },
      };
    }
    return {
      ok: false,
      driverError: `${label} exit ${result.status}`,
      stderr: stderrRaw,
      stdout: result.stdout ?? "",
      childStatus: { ...childStatusBase, phase },
    };
  }

  // Zero exit
  phase.serialization = `${label}-zero-exit`;
  if (!text) {
    return {
      ok: false,
      driverError: `${label} produced no output`,
      stderr: stderrRaw,
      childStatus: { ...childStatusBase, phase },
    };
  }

  try {
    const envelope = JSON.parse(text) as DriverEnvelope;
    childStatusBase.stdoutValidJson = true;
    childStatusBase.stdoutShapeValid = envelope !== null && typeof envelope === "object" && "success" in envelope;
    childStatusBase.envelopeBackend = envelope.backend ?? null;
    phase.serialization = `${label}-valid-json`;
    return {
      ok: true,
      result: envelope,
      stderr: stderrRaw,
      childStatus: { ...childStatusBase, phase },
    };
  } catch (e) {
    return {
      ok: false,
      driverError: `${label} produced invalid JSON: ${(e as Error).message}`,
      stdout: text.slice(0, 2000),
      childStatus: { ...childStatusBase, phase },
    };
  }
}

/**
 * Run the Python driver against a specific fixture copy. The driver
 * reads ACCESS_TEST_DB internally.
 */
function runPython(childFixturePath: string, casePath: string, variant: string): DriverResult | DriverError {
  const env = {
    ...pinnedEnv,
    ACCESS_TEST_DB: childFixturePath,
    PARITY_EXPORT_DIR: tmpdir(),
    PARITY_VARIANT: variant,
    PARITY_SOURCE_DB,
    PARITY_FIXTURE: childFixturePath,
  };
  return runChild(PYTHON, [PYTHON_DRIVER, casePath], env, "python");
}

/**
 * Run the ReScript runner against a specific fixture copy. The runner
 * reads ACCESS_TEST_DB internally.
 */
function runRescript(childFixturePath: string, casePath: string, variant: string): DriverResult | DriverError {
  const env = {
    ...pinnedEnv,
    ACCESS_TEST_DB: childFixturePath,
    PARITY_EXPORT_DIR: tmpdir(),
    PARITY_VARIANT: variant,
    PARITY_SOURCE_DB,
  };
  return runChild(NODE, [RS_RUNNER_JS, casePath], env, "rescript");
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

if (!existsSync(casesDir)) {
  console.error(`parity: cases directory does not exist: ${casesDir}`);
  process.exit(1);
}

const caseFiles = (() => {
  const all = readdirSync(casesDir)
    .filter((f) => f.endsWith(".json"))
    .sort();
  if (exactCase !== null) {
    const target = all.find((f) => f === exactCase || f === exactCase || join(casesDir, f) === resolve(casesDir, exactCase));
    if (!target) {
      console.error(`parity: --case "${exactCase}" not found in ${casesDir}`);
      process.exit(1);
    }
    return [target];
  }
  return all;
})();

// --require-read-only guard: abort before opening any DB if any case is mutating
if (requireReadOnly) {
  for (const caseFile of caseFiles) {
    const casePath = join(casesDir, caseFile);
    const caseObj: CaseFile = JSON.parse(readFileSync(casePath, "utf8"));
    if (caseObj.mutating === true) {
      console.error(`parity: --require-read-only: case ${caseFile} has mutating:true, aborting before DB open`);
      process.exit(1);
    }
  }
}

let passed = 0;
let mismatched = 0;
let errored = 0;
let skipped = 0;
const findings: Finding[] = [];

interface Finding {
  operation: string;
  case: string;
  diff: DiffEntry;
  stderr?: string;
  pythonChild?: ChildStatusDetail;
  rescriptChild?: ChildStatusDetail;
  backendMismatch?: string;
}

interface DiffEntry {
  path: string;
  expected: unknown;
  actual: unknown;
}

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
  const casePath = join(casesDir, caseFile);
  const caseObj: CaseFile = JSON.parse(readFileSync(casePath, "utf8"));
  const variant = (caseObj as CaseFile).variant ?? "odbc";

  // Plan 036 T4: kill any lingering MSACCESS.EXE before each COM case so
  // the 033-F-001 teardown crash from the previous ReScript child doesn't
  // leave Access holding the .accdb lock (otherwise the next python WinCom
  // child hits "You already have the database open"). No-op for ODBC.
  if (variant === "com" && process.platform === "win32") {
    try {
      execSync("taskkill /F /IM MSACCESS.EXE 2>nul", { stdio: "ignore", shell: "cmd.exe" });
    } catch {
      // taskkill exits 1 when no process matches; that's fine
    }
  }

  // Skip short-circuit: skip cases are excluded from matched/errored counts
  if (caseObj.skip === true) {
    skipped++;
    console.log(`  SKIP  ${caseFile} — ${caseObj.skipReason ?? "no reason provided"}`);
    continue;
  }

  const mutating = caseObj.mutating === true || Array.isArray(caseObj.setup);
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
      { ...pinnedEnv, ACCESS_TEST_DB: pyFixture, PARITY_EXPORT_DIR: tmpdir(), PARITY_VARIANT: variant },
      "python-prime",
    );
  }

  const pyResult = runPython(pyFixture, casePath, variant);
  const rsResult = runRescript(rsFixture, casePath, variant);

  // Persist case-level artifact with paired envelopes
  const pyChildStatus = (pyResult as DriverResult).childStatus ?? (pyResult as DriverError).childStatus;
  const rsChildStatus = (rsResult as DriverResult).childStatus ?? (rsResult as DriverError).childStatus;

  persistArtifact(
    `${caseFile.replace(/\.json$/, "")}-python.json`,
    JSON.stringify({
      case: caseFile,
      envelope: pyResult.ok ? pyResult.result : null,
      driverError: pyResult.ok ? null : (pyResult as DriverError).driverError,
      childStatus: pyChildStatus,
    }, null, 2),
  );
  persistArtifact(
    `${caseFile.replace(/\.json$/, "")}-rescript.json`,
    JSON.stringify({
      case: caseFile,
      envelope: rsResult.ok ? rsResult.result : null,
      driverError: rsResult.ok ? null : (rsResult as DriverError).driverError,
      childStatus: rsChildStatus,
    }, null, 2),
  );

  // Driver-level errors (non-zero exit, bad JSON) are reported as
  // mismatches with a "DRIVER" prefix; they're actionable.
  if (!pyResult.ok || !rsResult.ok) {
    errored++;
    const pyErr = pyResult as DriverError;
    const rsErr = rsResult as DriverError;
    const driverErr = pyResult.ok ? rsErr.driverError : pyErr.driverError;
    findings.push({
      operation: caseObj.operation,
      case: caseFile,
      diff: {
        path: "DRIVER",
        expected: pyResult.ok ? "ok" : "driver error",
        actual: rsResult.ok ? "ok" : "driver error",
      },
      stderr: pyResult.stderr ?? rsResult.stderr,
      pythonChild: pyChildStatus,
      rescriptChild: rsChildStatus,
    });
    console.log(`  ERROR  ${caseFile} — ${driverErr}`);
    continue;
  }

  // Backend identity check: COM must not silently fall back to ODBC
  const pyBackend = pyChildStatus?.envelopeBackend;
  const rsBackend = rsChildStatus?.envelopeBackend;
  let backendMismatch: string | undefined;
  if (pyBackend && rsBackend && pyBackend !== rsBackend) {
    backendMismatch = `python=${pyBackend}, rescript=${rsBackend}`;
  }

  const volatile = caseObj.volatileFields ?? [];
  const pyN = normalize(pyResult.result, volatile);
  const rsN = normalize(rsResult.result, volatile);

  const d = diff(pyN, rsN);

  // Record logical equality for diagnosis (NEVER as acceptance)
  const logicalEquality = d === null;
  if (pyChildStatus) pyChildStatus.logicalEquality = logicalEquality;
  if (rsChildStatus) rsChildStatus.logicalEquality = logicalEquality;

  if (d === null) {
    passed++;
    console.log(`  PASS  ${caseFile}`);
  } else {
    mismatched++;
    findings.push({
      operation: caseObj.operation,
      case: caseFile,
      diff: d,
      pythonChild: pyChildStatus,
      rescriptChild: rsChildStatus,
      backendMismatch,
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
console.log(`parity: ${caseFiles.length} cases, ${passed} matched, ${mismatched} mismatched, ${errored} errored, ${skipped} skipped`);

// Persist findings for step 6 review.
const findingsPath = join(__dirname, "..", "findings.json");
writeFileSync(findingsPath, JSON.stringify(findings, null, 2));

// Persist final run artifact with full provenance
const runArtifact: RunArtifact = {
  runId: RUN_ID,
  timestamp: new Date().toISOString(),
  casesDir,
  exactCase,
  gitSha: gitInfo?.sha,
  compiledArtifactPath: gitInfo?.artifactPath,
  phase: {},
  pythonChild: undefined,
  rescriptChild: undefined,
  setupStatus: "complete",
};
persistArtifact("run.json", JSON.stringify(runArtifact, null, 2));

if (mismatched > 0 || errored > 0) {
  process.exit(1);
}
process.exit(0);
