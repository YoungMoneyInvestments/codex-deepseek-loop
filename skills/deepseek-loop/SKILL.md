---
name: deepseek-loop
description: "Harden a plan with an independent DeepSeek-V4.1-Flash review, then build and cross-inspect the final code. Use for deepseek-loop, /deepseek-loop, or when a Claude Code or Codex workflow wants a cheap, fast independent reviewer seat; not for trivial edits."
---

# DeepSeek Loop

The current conversation owns requirements, planning and coordination, and is the default builder. DeepSeek-V4.1-Flash takes the independent reviewer seat: it adversarially reviews the plan before code exists, then inspects the final change set. The reviewer is a separate model from a separate provider — whoever built it never grades it.

## Resolve roles once

Identify the actual host from your runtime, not PATH, installed skills or the repository. Use `host=claude` in Claude Code and `host=codex` in Codex. If the runtime identity is unavailable, ask which host the user is using once.

| Host | Requirements, plan and build | Plan reviewer | Final inspector |
|---|---|---|---|
| Claude Code | Current Claude session | DeepSeek-V4.1-Flash | DeepSeek-V4.1-Flash (fresh run) |
| Codex | Current Codex session | DeepSeek-V4.1-Flash | DeepSeek-V4.1-Flash (fresh run) |

The reviewer model defaults to `deepseek-flash` (DeepSeek-V4.1-Flash) with thinking effort `high`. Honor explicit `model=deepseek-flash|deepseek-v4-pro` and `effort=low|high|max|none`. Require `DEEPSEEK_API_KEY` in the host environment; if it is missing, stop and ask the user to export it. Never fall back to a different model or reviewer silently.

The runner is `scripts/deepseek_review.py`, relative to this installed SKILL.md — copy its absolute path from the skill directory, never resolve it against the project being reviewed. Run it through the host's shell. It is standard-library Python (3.9+); no packages to install.

## Tunables

| Argument | Default | Meaning |
|---|---|---|
| `PLAN_FILE` / `plan` | `PLAN.md` | Plan path used throughout |
| `LOG_FILE` / `log` | `PLAN-REVIEW-LOG.md` | Append-only transcript of rounds, findings, dispositions and costs |
| `rounds` / `MAX_ROUNDS` | `3` | Maximum completed plan-review rounds |
| `effort` | `high` | DeepSeek thinking effort (`low`, `high`, `max`, `none`) |
| `MAX_FIX_ROUNDS` | `2` | Bounded build-fix attempts before reporting or taking over |
| `MAX_INSPECTION_ROUNDS` | `2` | Initial inspection plus one after accepted fixes |
| `inspect` | `on` | `off` only when the user explicitly opts out; record it |

Echo roles, paths, round limits and the reviewer model before starting. Preserve existing authorization: a request to plan does not authorize building; a request to plan and implement does.

## Phase 0 — Recon

For existing projects, inspect relevant code, dependencies, callers and writers of shared state so the plan and later review context are grounded. For greenfield work, research prior art and concrete failure modes when useful.

The reviewer cannot read the repository. Everything it sees is what you send: a plan plus files you inline with `--context` (interfaces, schemas, callers, configuration — material context, not the whole tree). Record what you chose not to include. Never include secrets, `.env` contents, tokens or credentials in the plan or context.

Present one assumptions ledger with source paths. Ask for corrections to material uncertainties as a batch. Resolve routine reversible choices yourself when the user has authorized the work; silence is not approval of an action requiring approval.

## Phase 1 — Settle requirements

Maintain a short visible decision map. Ask only about unresolved decisions that change the outcome; for each, give the recommendation, why it matters, and the cost of guessing wrong. Batch independent questions. If the code can answer, inspect it instead.

Write the resolved `PLAN_FILE` with goal and observable acceptance criteria, concrete approach, key decisions and non-goals, confirmed assumptions, and verification: exact proof command(s) and expected results. Start the append-only `LOG_FILE` with roles, reviewer model/effort, scope, authorization and round limits. Keep run artifacts (DeepSeek runner output) outside the checkout via `--artifacts`.

## Phase 2 — Independent plan review

Run one review round:

```bash
python3 "<skill-dir>/scripts/deepseek_review.py" review \
  --host claude --repo "$PWD" --plan PLAN.md \
  --context src/orders.py --context docs/schema.sql \
  --artifacts /tmp/deepseek-loop
```

(`--host codex` when started in Codex; add more `--context` paths as needed.)

The run prints progress and a final result JSON with `review.verdict`, findings, actual coverage, limitations, token usage, latency and a USD cost estimate for the run. Preserve the full result path and verdict in `LOG_FILE`. Append the cost to the log as well — it is part of the loop's value.

- **APPROVED:** no unresolved material defects. Approval is bound to the exact plan path and SHA256; any later plan edit invalidates it.
- **REVISE:** the host arbitrates every finding. Implement warranted plan changes, reject unsupported suggestions with reasons, and record dispositions. For the next round, write the dispositions (and prior findings) to a feedback file and re-run with `--feedback <file>`; never relitigate resolved points without new evidence.
- **BLOCKED / failed process / malformed result:** never count as approval. Report the actual missing evidence or operational failure; repair and re-run deliberately, not blindly. A failed API call is not a verdict.

Stop at `MAX_ROUNDS`. Present unresolved findings and the host's position instead of manufacturing convergence. A changed plan requires another review. Before building, verify the approval:

```bash
python3 "<skill-dir>/scripts/deepseek_review.py" check \
  --host claude --repo "$PWD" --approval <run-dir>/result.json
```

If the user explicitly chooses to proceed without an approval, record that override in the log; never label it approved.

## Phase 3 — Build and inspect

The host implements the approved plan with its normal tools. Capture the pre-build commit (`git rev-parse HEAD`) before editing; preserve unrelated user work. Run the agreed proof checks and record their output in the log.

Then commission the independent inspection of the final change set:

```bash
python3 "<skill-dir>/scripts/deepseek_review.py" inspect \
  --host claude --repo "$PWD" --plan PLAN.md --base <pre-build-commit> \
  --context src/orders.py \
  --artifacts /tmp/deepseek-loop
```

The runner computes the change manifest (tracked, untracked, deleted), the tracked diff and the contents of new files, and sends them to DeepSeek. Add `--context` for callers, writers or schemas that the diff alone does not cover. If the code changes during the run, the runner fails the inspection — re-run it on the final code.

Arbitrate findings as in Phase 2. Accepted fixes get a fresh inspection (same `--base`) and rerun proof checks; batch confirmed fixes into one revision. Never claim DeepSeek ran tests — it cannot; the host's proof output is the evidence.

If the host takes over material coding, it has become the builder for those edits; they need a fresh inspection like any other change. If the inspection budget is exhausted, report remaining findings and unreviewed edits explicitly for the user's decision.

## Reporting

Present the final diff, proof results, inspection coverage, unresolved findings and rounds used — plus the accumulated cost from the logs. Honor existing commit/push authorization; otherwise leave the concrete diff ready for sign-off. External publication is never implied merely by running the loop.
