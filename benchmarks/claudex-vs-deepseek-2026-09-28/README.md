# Claudex-loop vs Codex-DeepSeek-loop benchmark

Runnable head-to-head for the review stages of both skills. It uses eight tiny,
synthetic Git fixtures: three plan reviews, four defective code inspections,
and one clean inspection. No private repository code is sent to either model.

## What it measures

- Defect recall, severity-weighted recall, seeded-defect precision, severity
  accuracy, and correct `APPROVED`/`REVISE` verdicts.
- Completion rate, wall time, model identity, measured token usage, and clearly
  labeled provider-reported or runner-estimated costs.
- Three repetitions in randomized interleaved order by default.

The primary quality score is preregistered in code: 50% weighted recall, 25%
precision, 15% verdict accuracy, and 10% severity accuracy. A lead must exceed
two points; cost and latency stay separate.

This isolates the meaningful difference between the skills: the independent
reviewer. Both loops can use the same Codex builder, so an end-to-end build test
would mostly retest Codex and add noise. Add that phase only if reviewer results
are tied and the feedback's effect on repairs remains uncertain.

## Run

From this directory:

```bash
python3 benchmark.py self-test
python3 benchmark.py doctor
python3 benchmark.py prepare
python3 benchmark.py run --dry-run
python3 benchmark.py run --allow-paid-deepseek
python3 benchmark.py score
python3 benchmark.py report
```

The default work directory is outside the checkout under the user's cache
directory. `prepare` refuses a non-empty work directory. Use a new `--work-dir`
for a new run; this prevents accidental mixing or overwrite. `run` resumes by
job ID and keeps failures stopped unless `--retry-failed` is explicitly
supplied. `report` also writes into that work directory unless `--output` is
given, so a rerun does not overwrite this published report.

DeepSeek calls are disabled unless `--allow-paid-deepseek` is supplied. The
runner uses `DEEPSEEK_API_KEY` if present; otherwise it reads the existing
macOS Keychain item named `codex-deepseek` without printing or copying its value
into artifacts. Each call is capped at 8,192 output tokens by default and API
retries are disabled; DeepSeek's one JSON parse retry can still make a second
billable call. Claudex uses the installed Claude CLI and its policy-selected
reviewer.

The run preflight checks both the DeepSeek key reference and Claude CLI login
before starting either side. This prevents randomized order from spending on
one system when the other cannot run.

## Fairness contract

- Same plan, base commit, candidate diff, repetition count, and randomized job
  order for both systems.
- Claudex uses its native read-only repository access. DeepSeek receives the
  plan, tracked diff, new-file contents, and every declared context file. This
  tests each skill as shipped; it does not claim identical transport.
- Ground truth remains outside generated fixture repositories, so reviewers do
  not receive answer keys.
- The scorer assigns each finding to at most one seeded contract defect using
  deterministic keyword rules. This prevents one broad finding from earning
  credit for several defects. These automated matches are not manual
  adjudication; inspect `RESULTS.jsonl` before making broader claims.
- Primary quality and completion use each job's first attempt. Later retries
  remain in the ledger for diagnostics and cost, but cannot repair the score.
- Quote results only with `RESULTS.jsonl`, `SUITE.json`, `SCORES.json`, and
  `RUN-CONFIG.json`. The config records runner hashes, source heads, observed
  models, caps, and retry state. Results are suite- and configuration-specific.

## Cases

| Stage | Case | Seeded risk |
|---|---|---|
| Plan | Archive install | Missing hash and link/traversal controls |
| Plan | Ledger transfer | Non-atomic writes and late idempotency record |
| Plan | Market validation | Wrong session boundary and future leakage |
| Inspect | Tenant cache | Cross-tenant cache key leak |
| Inspect | ZIP install | Zip Slip/path escape |
| Inspect | Ledger write | Binary float and partial balance update |
| Inspect | Receipt parser | Blank line resets Order ID filtering |
| Inspect | Bounded retry | Clean control; should approve |

## Interpreting a winner

Use `REPORT.md` task by task. One system can win quality while the other wins
cost or speed. Do not convert a small synthetic result into a general model
ranking. A failed provider call is operational failure for that run, not a
review verdict.

## Published evidence

- `REPORT.md`: readable comparison and per-run table.
- `RESULTS.jsonl`: sanitized structured findings for all 48 jobs. Prompts,
  hidden reasoning, local paths, and secrets are excluded.
- `SCORES.json`: scored rows plus aggregates.
- `SUITE.json`: sanitized randomized job manifest and environment fingerprint.
- `RUN-CONFIG.json`: exact initial and retry settings.
