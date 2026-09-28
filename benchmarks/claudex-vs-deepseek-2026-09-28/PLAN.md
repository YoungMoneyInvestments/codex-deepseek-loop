# Delivery plan

## Goal

Create a reproducible benchmark that compares the shipped review stages of
`claudex-loop` and `codex-deepseek-loop` on varied plan and code defects.

## Acceptance criteria

- Both systems receive the same synthetic task, base commit, candidate diff,
  repetition count, and randomized interleaved order.
- At least three plan-review cases, four defective code-inspection cases, and
  one clean control cover security, money/data integrity, tenancy, parsing, and
  time-series validation.
- Ground truth is hidden from generated fixture repositories.
- Scoring reports defect recall, seeded precision, severity and verdict
  accuracy, completion, latency, measured tokens, and labeled cost data.
- Provider failures remain failures, not verdicts. Runs are resumable by job ID.
- Paid DeepSeek calls require an explicit command flag, use the existing secret
  reference without printing it, disable transport retries, and cap output.
- A no-network self-test, environment doctor, fixture preparation, and command
  dry-run succeed.

## Non-goals

- No claim that eight synthetic fixtures rank the underlying models generally.
- No end-to-end builder comparison: both skills can use the same Codex builder,
  which would confound reviewer quality with shared build performance.
- No dollar-cost claim when a provider or subscription does not report it.

## Proof

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile benchmark.py fixtures.py
PYTHONDONTWRITEBYTECODE=1 python3 benchmark.py self-test
python3 benchmark.py doctor
```

Manual proof: prepare the suite, inspect `suite.json`, and dry-run all 48
randomized commands before authorizing live DeepSeek spend.
