// ---------------------------------------------------------------------------
// Lint parity cases against cases.schema.json (JSON Schema 2020-12).
//
// Validates every JSON file in parity/cases/ against cases.schema.json.
// Catches top-level drift (operation enum, variant enum, mutating/volatileFields
// shape) before any runner work. Per-op args shapes are NOT validated here —
// the runner validates those at runtime against the live facade signature.
//
// Usage:
//   node parity/lint-cases.mjs
//
// Exits 0 on success, 1 on any validation failure (with a clear error report).
// ---------------------------------------------------------------------------

import { readdirSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import Ajv from "ajv";

const here = dirname(fileURLToPath(import.meta.url));
const CASES_DIR = join(here, "cases");
const SCHEMA_PATH = join(here, "cases.schema.json");

const schema = JSON.parse(readFileSync(SCHEMA_PATH, "utf8"));
const ajv = new Ajv({ allErrors: true, strict: false });
const validate = ajv.compile(schema);

const caseFiles = readdirSync(CASES_DIR)
  .filter((f) => f.endsWith(".json"))
  .sort();

let failed = 0;
const errors = [];

for (const caseFile of caseFiles) {
  const casePath = join(CASES_DIR, caseFile);
  let caseObj;
  try {
    caseObj = JSON.parse(readFileSync(casePath, "utf8"));
  } catch (e) {
    failed++;
    errors.push({ case: caseFile, message: `invalid JSON: ${e.message}` });
    continue;
  }

  if (!validate(caseObj)) {
    failed++;
    errors.push({
      case: caseFile,
      message: ajv.errorsText(validate.errors, { separator: "\n  " }),
    });
  }
}

if (failed > 0) {
  console.error(`parity lint: ${failed} of ${caseFiles.length} cases failed`);
  for (const e of errors) {
    console.error(`  ${e.case}: ${e.message}`);
  }
  process.exit(1);
}

console.log(`parity lint: ${caseFiles.length} cases OK`);