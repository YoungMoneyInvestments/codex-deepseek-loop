# Runtime reference

## Requirements

- Python **3.9+** (standard library only — no packages to install). Tested on 3.9 and 3.11–3.14.
- `git` on PATH (or `GIT=/path/to/git` for machines whose PATH git is a stub).
- `DEEPSEEK_API_KEY` exported in the host session's environment. Create one at `platform.deepseek.com`.
- `DEEPSEEK_BASE_URL` optional (default `https://api.deepseek.com`).

## Install locations

| Host | Skill directory | Invocation |
|---|---|---|
| Claude Code | `~/.claude/skills/deepseek-loop/` | `/deepseek-loop` (or `/claude-deepseek-loop:deepseek-loop` via plugin) |
| Codex | `~/.agents/skills/deepseek-loop/` | `$deepseek-loop` |

Manual install copies the whole `skills/deepseek-loop/` directory (SKILL.md, `references/`, `scripts/`) into the host's skill directory. The runner is resolved from the installed skill directory, so keep the directory layout intact.

## DeepSeek API contract used by the runner

- Endpoint: `POST https://api.deepseek.com/chat/completions` (OpenAI format; an Anthropic-format base URL also exists).
- Model IDs: `deepseek-flash` (DeepSeek-V4.1-Flash, 1M context, 384K max output, text+image input — the reviewer default) and `deepseek-v4-pro` (being phased out by DeepSeek in favor of V4.1-Flash).
- Thinking mode is enabled by default; the runner sends `thinking: {type: enabled}` with `reasoning_effort` of `low`/`high`/`max` (default `high`). `effort=none` disables thinking mode.
- `response_format: {type: json_object}` requests strict JSON; the runner validates the returned review against a fixed schema and fails closed on malformed output. DeepSeek's JSON mode can occasionally return empty content — the runner retries once, then reports the failure honestly.
- `usage` reports `prompt_cache_hit_tokens`, `prompt_cache_miss_tokens` and `completion_tokens`; the runner converts them to off-peak and peak USD estimates.
- Retries: bounded retries on 429/5xx/network errors with backoff (5s, 15s, 45s). 4xx errors other than 429 fail immediately. Override backoff for tests with `DEEPSEEK_LOOP_RETRY_BACKOFF`.

## Pricing used for estimates (USD per 1M tokens)

| Model | Input cache hit | Input cache miss | Output |
|---|---|---|---|
| deepseek-flash off-peak | $0.003 | $0.15 | $0.60 |
| deepseek-flash peak | $0.006 | $0.30 | $1.20 |
| deepseek-v4-pro off-peak | $0.022 | $0.66 | $1.98 |
| deepseek-v4-pro peak | $0.044 | $1.32 | $3.96 |

Peak hours are 01:00–04:00 and 06:00–10:00 UTC, Monday–Friday, excluding Chinese public holidays; everything else, including weekends, is off-peak. Source: `api-docs.deepseek.com/quick_start/pricing`. The runner prints both figures; the invoice follows DeepSeek's clock.

## What leaves your machine

The runner sends the plan text, change manifest, tracked diff, new-file contents and any `--context` files to the DeepSeek API. Nothing else. It never reads or sends `.env` files on its own, never logs the API key, and keeps run artifacts (prompt, response, reasoning, diff, result) in an artifacts directory outside the target checkout. Do not put secrets, credentials or private keys into plans, context files or source you pass in — and note that the reviewer is a third-party service: review DeepSeek's current data policy for anything sensitive.

## Limits

- The reviewer has no repository access; review quality is bounded by the context you send.
- Structured-output validation rejects broken transport and inconsistent verdicts but cannot prove a review is correct; the host arbitrates findings.
- Prompt size is capped by `--max-input-chars` (default 3,000,000 characters, a safety margin under the 1M-token context). Oversized runs fail with instructions instead of silently truncating. Per-file context is capped by `--max-file-chars` (default 300,000) with an explicit truncation marker.
- A review is evidence, not a proof. Repository tests and proof commands remain the source of truth.
