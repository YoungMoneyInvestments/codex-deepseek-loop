# Validation

Development date: 2026-09-28. Tests ran in disposable fixture repositories; no production repository was modified by the live smoke tests.

## Automated checks

- `python3 scripts/validate.py` — skill frontmatter, local references, reviewer runner presence and plugin manifests: **passed**.
- `python3 -m unittest discover -s tests` — **25 tests passed** on Python 3.9.6 and Python 3.12.11 (macOS). The suite covers role resolution for both hosts, retry on 503, parse-retry on empty content, fail-closed schema validation, immediate failure on 4xx, missing API key, prompt caps, artifacts isolation, approval binding to the plan SHA256, change-manifest coverage (modified / untracked / deleted), diff and new-file inlining, mid-run mutation detection, and both hosts' CLI plumbing.
- No network access and no model quota are used by the suite: the DeepSeek API is replaced by a local mock HTTP server and Git fixtures are disposable temporary repositories.
- CI (`.github/workflows/tests.yml`) runs the same checks on Linux, macOS and Windows with Python 3.11 and 3.13.

## DeepSeek API contract check

- `GET https://api.deepseek.com/models` (with the project's key) returned `deepseek-flash` — DeepSeek-V4.1-Flash, 1M-token context, 384K max output, effort levels `low`/`high`/`max` — alongside `deepseek-v4-pro`. The runner's default model id is verified against the live API, not assumed.

## Live model checks (real API calls)

| Check | Result |
|---|---|
| Plan review of a deliberately unsafe backup-rotation plan (delete-before-upload ordering, stale file reference, no upload verification), with the current script sketch as `--context` | **REVISE** — 10 findings (2 high): caught both seeded defects with line references (`scripts/backup.py:12,15-17,19` — the prune loop runs before the upload and `newest` is a stale reference into the pre-deletion list) plus 8 further evidence-backed findings. 28.6 s; 954 input / 5,867 output tokens (3,413 reasoning); **$0.0037 off-peak / $0.0073 peak** |
| Inspection of a retry-cap change: base commit + modified `client.py` with an off-by-one (2 attempts instead of the plan's 3) + an untracked test asserting the buggy count | **REVISE** — 3 findings (2 high): identified that the implementation makes 2 attempts where the plan requires 3, that the new test "blesses the implementation rather than the required behavior" by asserting `len(calls) == 2`, and a latent implicit-`None` exit path in the retry loop. 9.3 s; 1,256 input / 1,954 output tokens (844 reasoning); **$0.0014 off-peak / $0.0027 peak** |

Both runs used `deepseek-flash` at `effort=high` through the hosted API, returned schema-valid structured reviews on the first attempt (0 retries), and stayed well inside the runner's prompt caps. Combined cost of both live checks: **≈ $0.005 off-peak / $0.010 peak**.

The fixtures exercised transport, binding and obvious-defect detection — not comparative model quality. A green verdict is not proof of exhaustive review, and the live checks do not establish that this reviewer is better than any other; they establish that the loop works as designed and reports honestly.

## Limits

- Live checks ran on macOS (Python 3.12.11) against the hosted DeepSeek API; CLI versions and pricing can change, and the runner prints its own live cost estimate every run.
- Structured-output validation rejects broken transport and inconsistent verdicts but cannot prove a model's findings are correct.
- The reviewer has no repository access: review quality is bounded by the plan, diff and `--context` files the host provides.
