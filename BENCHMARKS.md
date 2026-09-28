# Why DeepSeek-V4.1-Flash is the reviewer seat

This document explains the model choice behind the loop, from measured numbers — and states its limits. All figures were retrieved on **2026-09-28** from the sources linked at the bottom; vendor-reported scores are marked, and independent measurements are attributed.

## Direct loop reviewer benchmark

We also ran a controlled first-party comparison of this repository against Young Money Investments' policy-selected adaptation of [Chase AI's `claudex-loop`](https://github.com/chaseai-yt/claudex-loop) (MIT). The suite used eight synthetic, secret-free plan and code-review cases, three repetitions, and randomized interleaving: 24 jobs per loop, 48 total. Both systems reviewed the same fixture repository, plan, Git base, and candidate state through their native delivery paths. Both were scored against the same answer key, which was not added to fixture repositories or reviewer request payloads.

| Metric | Claudex loop | Codex DeepSeek loop |
|---|---:|---:|
| Composite quality score | 85.4 | 83.3 |
| Seeded defects found | 39/39 | 39/39 |
| Clean-control accuracy | 100.0% | 100.0% |
| Expected-verdict accuracy | 91.7% | 100.0% |
| Severity accuracy | 89.7% | 89.7% |
| Seeded-answer-key precision | 50.6% | 37.1% |
| Job completion (no benchmark reruns) | 24/24 | 24/24 |
| Median latency | 16.8 seconds | 10.7 seconds |
| Run cost | $0.9780 CLI notional | At least $0.0399 off-peak / $0.0798 peak |

The preregistered quality rule required a lead greater than two points. Claudex cleared it by 2.13 points, driven by fewer findings that could not be matched to the seeded answer key. Automated one-to-one keyword matching credited both reviewers with all 39 seeded defects, and both approved every clean control. DeepSeek's median latency was 36% lower (10.7 seconds versus 16.8 seconds) and it returned the expected verdict on every run. Claudex returned `BLOCKED` instead of expected `REVISE` on two plan runs while still finding every seeded defect in those runs.

These are not audited false-positive rates. An unmatched finding may be a valid extra defect, an overlapping restatement, or noise. The raw structured findings are published for inspection. Independent review found that the original scorer could credit one finding to more than one defect; the published scores were recomputed after enforcing one-to-one matching. Claude's dollar figure is an API-equivalent CLI value from a Max subscription, not a billed invoice. One DeepSeek job used a JSON parse retry, and the tested runner kept only the final response's usage, so its 21,576 input and 64,262 output tokens and dollar amounts are lower bounds. The runner is fixed in this change to accumulate future retry usage.

Claudex used native read-only repository access. DeepSeek received a bundled plan, diff, new files, and declared context. The results measure each skill as shipped, not identical transport. The suite measures reviewer behavior, not builder quality or complete project delivery.

The tested source heads were `2a82e6e7d9d0f320b5d9069acf50740926f1ef0c` for the YMI Claudex adaptation and `853a1467a25a113d74ec4a5ba2ad08db6ae65f7d` for this repository. The tested Claudex source lives in a private multi-skill repository, so its SHA identifies the snapshot but public readers cannot independently audit it. Claudex plan reviews used observed `claude-sonnet-4-6`; inspections used `claude-opus-5-5`. DeepSeek used observed `deepseek-flash` at high effort with an 8,192-token output cap and no HTTP retries. Runner hashes, scorer identity, configuration, and all 48 structured reviews are included with the evidence.

Fixtures, scoring code, sanitized structured reviews, per-run scores, configuration, and report are in [`benchmarks/claudex-vs-deepseek-2026-09-28/`](benchmarks/claudex-vs-deepseek-2026-09-28/).

## TL;DR

| | DeepSeek-V4.1-Flash | Claude Fable 5.1 | GPT-5.6 Sol | GPT-6 Astra |
|---|---|---|---|---|
| Terminal-Bench 2.1 (agentic coding) | **90.6** | — (Opus-5.0: 89.1) | 88.8 | — |
| DeepSWE v1.1, resolved | **74.2** | — (Opus-5.0: 74.0) | 73.0 | — |
| AutomationBench | **54.8** | — (Opus-5.0: 50.3) | 45.8 | — |
| Intelligence Index (Artificial Analysis) | 39 | ≈53 | — | — |
| Output speed (tokens/s) | **221.3** | 68.8 | — | — |
| Price per 1M tokens (in / out) | **$0.15 / $0.60** off-peak ($0.30 / $1.20 peak) | $10 / $50 | $5 / $30 | $10 / $50 |
| Context window | 1M | 1M | — | 1.05M |
| Weights | **MIT, open** | closed | closed | closed |

On the agentic-coding evaluations that closest proxy the reviewer's job — read a plan or diff, run an end-to-end task, find what breaks — V4.1-Flash matches or beats the frontier flagships **while costing 19×–72× less per loop and running ~3.2× faster**. That is the whole argument, and it is a cost-adjusted one: the aggregate intelligence index still favors the frontier, and the hardest long-horizon tasks still do too (see [Where it trails](#where-it-trails)).

## The reviewer seat is a different job than the builder seat

The loop keeps the frontier model where it is strongest — planning and authoring long-horizon code in the host session — and puts DeepSeek where the work is bounded and adversarial: read what the host produced, attack it, report evidence. That seat values:

1. **Agentic judgment on code** — finding defects in plans and diffs, not writing the feature.
2. **Large context** — whole plans plus diff plus manifest plus new files in one pass (1M tokens).
3. **Speed** — the loop is interactive; review turns should not dominate wall-clock time.
4. **Cost per round** — cheap rounds mean you actually run multiple rounds of scrutiny instead of one expensive pass.
5. **No file access required** — the host assembles the context; the reviewer only reasons over it (which is also a smaller attack surface).

The closest public evidence for (1) is the agentic benchmark family. For (2)–(5), the numbers are direct.

## Head-to-head: the evaluations that matter for review

DeepSeek's model card publishes a max-reasoning-effort comparison against the frontier flagships. Scores within 0.3 are considered equivalent by the authors. **(vendor-reported)**

| Benchmark | DS-V4.1-Flash | Claude Opus-5.0 | GPT-5.6 Sol |
|---|---|---|---|
| Terminal-Bench 2.1 | **90.6** | 89.1 | 88.8 |
| Terminal-Bench 3.0 | 30.0 | **43.3** | 34.4 |
| Terminal-Bench 4.0 | 31.2 | **51.8** | 39.9 |
| DeepSWE v1.1 (resolved) | **74.2** | 74.0 | 73.0 |
| AutomationBench | **54.8** | 50.3 | 45.8 |
| Agent's Last Exam | **31.8** | 28.6 | 26.7 |
| CyberGym | **88.1** | — | 84.5 |
| HLE with tools | **63.9** | 63.6 | — |
| GPQA Diamond | 90.9 | **93.4** | **94.1** |
| Humanity's Last Exam | 36.8 | **56.3** | 44.5 |
| ProgramBench (Almost@1) | 20.3 | **37.0** | 23.0 |

The pattern: **on agentic execution — terminal work, end-to-end software tasks, automation — V4.1-Flash is at or ahead of both flagships. On raw knowledge and the very hardest long-horizon synthesis, it trails.** That is precisely the split the loop exploits: the frontier model authors; DeepSeek grades. (For transparency: V4.1-Flash was evaluated through the official Claude Code harness at 69.8 and the Codex harness at 65.6 on DeepSWE v1.1 — the same hosts this repository runs inside.)

## Independent measurements (Artificial Analysis)

| Metric | Result |
|---|---|
| Intelligence Index | **39** — #7 of 116 in its large open-weight comparison class (class median: 18) |
| Output speed | **221.3 tok/s** — #4 of 116; open-weight-class median 85.3 tok/s; Claude Fable 5.1 measures 68.8 tok/s |
| Cost per Intelligence Index task | **$0.27** |
| Cache discount | **98%** (cache-hit input at $0.003/1M off-peak) |
| Context window | 1M tokens |
| Architecture | 552B-param MoE, 16B active during decode; KV cache ~1/4 of V4-Flash's |
| License | **MIT** — open weights (commercial use permitted) |

## Cost math for one full loop

Assumed shape of a medium feature loop (state your own numbers if yours differ): two plan-review rounds plus one final inspection ≈ **215K input + 24K output tokens**. Conservatively billed as all cache-miss:

| Reviewer model | Cost per loop | 20 loops/month |
|---|---|---|
| **DeepSeek-V4.1-Flash (off-peak)** | **$0.047** | **$0.93** |
| DeepSeek-V4.1-Flash (peak) | $0.093 | $1.87 |
| GPT-5.6 Sol ($5/$30) | $1.80 | $35.90 |
| GPT-6 Astra / Claude Fable 5.1 ($10/$50) | $3.35 | $67.00 |

Two amplifiers:

- **Automatic caching.** Input that repeats between rounds (the plan, the context files) bills at the cache-hit rate: re-sending 215K cached input costs **$0.000645** off-peak. Additional review rounds are effectively free.
- **Speed.** 24K output tokens take ≈ **109 seconds** at 221 tok/s, vs ≈ **349 seconds** at Fable 5.1's 69 tok/s.

And one subtraction: the reviewer does not need a second frontier subscription. The host seat you already pay for stays the host; grading moves to metered pennies.

## Why the loop contains reviewer error

No model is right because of its benchmark score. The loop is designed so the reviewer's mistakes are bounded:

- **Whoever built it never grades it** — review always runs on a different model from a different provider than the author.
- **The host adjudicates** — findings are proposals. Warranted ones are implemented; unsupported ones are rejected with reasons recorded in the log.
- **Bindings fail closed** — approvals are tied to the plan hash or the exact change manifest; any later edit invalidates them. Mid-run code changes fail the inspection.
- **Proof commands stay sovereign** — DeepSeek cannot run tests, and a green verdict is not a green test suite. The host's actual proof output is the evidence.
- **Bounded rounds** — the loop stops at a round cap and presents remaining disagreement rather than manufacturing convergence.

## Where it trails

- **Hardest long-horizon terminal work** (Terminal-Bench 3.0/4.0) and **large-synthesis tasks** (ProgramBench) still favor the frontier flagships. Those are authoring workloads — the seat the host keeps.
- **Raw knowledge** (HLE without tools: 36.8 vs Opus-5.0's 56.3) is not V4.1-Flash's strength; reviews should lean on provided evidence, exactly as the runner's instructions do.
- **JSON-mode quirk**: DeepSeek's JSON mode can occasionally return empty content; the runner retries once and then fails honestly rather than inventing a verdict.
- **No repository access**: review quality is bounded by the context the host sends.
- Scores in the model-card head-to-head table above are **vendor-reported** from DeepSeek's model card; the Artificial Analysis figures are independent. The direct synthetic comparison above is first-party evidence, not a third-party benchmark. Treat all three evidence classes separately.

## Sources

- DeepSeek — [Introducing DeepSeek-V4.1-Flash](https://www.deepseek.com/en/news/deepseek-v4-1-flash/) (Sept 9, 2026) and [model card / technical report](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash) (benchmark tables, architecture, MIT license)
- DeepSeek — [API pricing](https://api-docs.deepseek.com/quick_start/pricing/) (models `deepseek-flash` / `deepseek-v4-pro`, off-peak vs peak, cache pricing)
- Artificial Analysis — [DeepSeek V4.1 Flash](https://artificialanalysis.ai/models/deepseek-v4-1-flash) (Intelligence Index, speed, cost per task, cache discount) and [Claude Fable 5.1](https://artificialanalysis.ai/models/claude-fable-5-1) (speed, pricing)
- OpenAI — [GPT-6 Astra](https://openai.com/index/gpt-6-astra/) ($10/$50) and Artificial Analysis GPT-5.6 family pricing ($5/$30 Sol, $2.5/$15 Terra, $1/$6 Luna)
- DeepSeek — [Thinking mode](https://api-docs.deepseek.com/guides/thinking_mode) and [JSON output](https://api-docs.deepseek.com/guides/json_mode) guides (runner contract)

*Prices and scores move. Re-check the sources before quoting them; the runner prints its own live cost estimate on every call.*
