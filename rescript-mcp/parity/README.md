README — parity harness
=======================

Differential parity harness for the ReScript port (`rescript-mcp/`) vs the
Python original (`src/ms_access_mcp/`). Each facade operation from
`rescript-mcp/src/Services/Facade.res` is exercised against both
implementations on the same `.accdb` fixture, the JSON envelopes are
normalized, and the differ compares them.

Layout
------
- `cases/<operation>.json` — one file per facade op (17 ops total).
  Each carries `operation`, `args`, `variant: "odbc"`, `mutating: bool`,
  optional `volatileFields` (dropped from the diff).
- `cases.schema.json` — JSON Schema (draft-07) for case files. Catches
  top-level drift (operation enum, variant enum, mutating/volatileFields
  shape) before any runner work. Per-op `args` shapes are NOT constrained
  here — the runner validates those at runtime against the live facade
  signature.
- `lint-cases.mjs` — validator: reads every `cases/*.json`, runs it
  through ajv against `cases.schema.json`, exits 0/1 with a precise
  error report.
- `../scripts/parity_driver.py` — Python driver; prints one JSON envelope
  per case to stdout.
- `run.mjs` — orchestrator: copies fixture per side for `mutating: true`
  cases, runs both children, normalizes, differs, prints summary.
- `runRescript.mjs` — ReScript child runner; calls into compiled
  `Services/Facade.res`.
- `normalize.mjs` — shared normalizer (key sort, int-valued-float
  canonicalization, Windows-path normalization, float tolerance 1e-9,
  ISO timestamps, `volatileFields`).
- `findings.md` — every real mismatch recorded here with operation,
  diff, suspected side, and owner.

Run
---
```
cd rescript-mcp
pnpm lint:cases   # fast pre-check: schema-validate every case
pnpm parity       # full run: both children, normalize, diff, summary
```

On Windows with `ACCESS_TEST_DB` set to
`D:\code\python\ms-access-mcp-server\tests\integration\fixtures\test_db.accdb`,
both children run against per-side copies of the fixture.

On Windows with `ACCESS_TEST_DB` set to
`D:\code\python\ms-access-mcp-server\tests\integration\fixtures\test_db.accdb`,
both children run against per-side copies of the fixture.

Off-Windows, ODBC driver is unavailable → runner skips cleanly with
exit 0.

Adding cases for new facade ops
- Author a JSON file in `cases/<op>.json` with `operation`, `args`,
  `variant`, `mutating`. The runner does the connect/disconnect for you.
- `operation` MUST be one of the 17 facade ops (enforced by
  `cases.schema.json`; run `pnpm lint:cases` to validate).
- `variant` MUST be `"odbc"` for v1.
- If the response contains paths or timestamps that differ between
  sides, add the field name(s) to `volatileFields`.

Mutation test
- Edit `Facade.res` (rename a response key, flip a constant, etc.),
  re-run parity, observe mismatch, revert. Step 5 of plan 007 proves
  the harness detects drift.