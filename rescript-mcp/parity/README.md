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
pnpm parity
```

On Windows with `ACCESS_TEST_DB` set to
`D:\code\python\ms-access-mcp-server\tests\integration\fixtures\test_db.accdb`,
both children run against per-side copies of the fixture.

Off-Windows, ODBC driver is unavailable → runner skips cleanly with
exit 0.

Adding cases for new facade ops
- Author a JSON file in `cases/<op>.json` with `operation`, `args`,
  `variant`, `mutating`. The runner does the connect/disconnect for you.
- If the response contains paths or timestamps that differ between
  sides, add the field name(s) to `volatileFields`.

Mutation test
- Edit `Facade.res` (rename a response key, flip a constant, etc.),
  re-run parity, observe mismatch, revert. Step 5 of plan 007 proves
  the harness detects drift.