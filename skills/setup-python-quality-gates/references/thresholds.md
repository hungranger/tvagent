# Thresholds (Phases 1–2): measure, then propose

Research-then-ask. Never propose a number without measuring it first — the
skill computes a baseline from the repo's *current* reality, then asks the
user to confirm or edit it. Greenfield (near-zero code) skips straight to
strict canonical defaults since there is no legacy debt to baseline against.

| Gate | Measured by | Parse recipe | Proposed baseline (legacy) | Proposed baseline (greenfield) |
|---|---|---|---|---|
| Coverage floor | `pytest --cov --cov-report=term-missing` (or `pytest --cov --cov-report=json` for a machine-readable number) | Read the `TOTAL` line's percentage, or `coverage.json`'s `totals.percent_covered` | `floor(current %)` | `92` |
| Complexity cap (mccabe C901) | `ruff check --select C901 --statistics .` | Statistics output lists each violated function's complexity; take the max reported | current worst function's complexity | `10` |
| Dead code | `vulture <src> <tests> --min-confidence 60` | Count findings at the default confidence; if the repo is noisy, this is a signal to raise confidence, not to skip the gate | `60` (default, adjust down only if it fires false positives worth allowlisting) | `60` |
| Type strictness | `pyright --outputjson` (parse `summary.errorCount` per mode) or `pyright --stats` | Run once at `strict`; if it fails, step down through `standard` → `basic` until one passes cleanly, that passing mode is the baseline | the mode the code already passes at zero errors, **plus a documented graduate-to-strict step** in the written docs | `strict` |
| Mutation floor (L2+, optional) | first `mutmut run` on the repo, then `mutmut results` / `mutmut export-cicd-stats` | score = killed / (killed + survived) from the CI-cicd-stats JSON | that first run's score, not blocking on day 1 | same — first run's score (mutation testing has no "zero debt" state to start strict at) |

## Measure → propose → confirm loop

For each gate:

1. Run the measuring command above; if the tool isn't installed, install it
   into the project's dev dependency group first, using the detected
   package manager (`uv add --dev <tool>`, `poetry add --group dev <tool>`,
   etc.) — never run a tool that isn't declared as a dependency.
2. Compute the baseline per the table.
3. Show it as "current X → proposed floor/cap Y" and ask the user to
   confirm or type a different number. Example prompts:
   - "current coverage 76% → floor 76? or aim higher?"
   - "worst complexity is 14 → cap 14 now, or set a tighter number to ratchet toward?"
   - "strict pyright fails on 40 files → start at `basic`, ratchet up later?"
4. Record the confirmed value against its `{{TOKEN}}` (see
   `templates/TOKENS.md`) for Phase 4 rendering.

## Rules baked in

- **Greenfield → strict canonical defaults.** No legacy debt, so start at
  the tight numbers (coverage 92, complexity 10, pyright strict, vulture 60).
- **Legacy → baseline = current reality.** The ratchet (`gate_ratchet.py`,
  see `anti-gaming.md`) locks it from here forward; it only tightens, never
  loosens. This is what avoids a day-one wall of red.
- **Every proposed number is confirmable** — never silently apply a
  computed baseline; always show measured-vs-proposed and let the user edit.
- **pyright on legacy is the sharp edge**: there is no native "baseline
  file" for pyright the way there sort of is for coverage. Start at the
  strictness mode the code already passes with zero errors; document the
  step-by-step graduation path to `strict` in the installed docs; the
  ratchet enforces the *mode* never regressing (see `check_pyright` in
  `gate_ratchet.py`).
