# Loop benchmark report

Quality is a tie within the preregistered 2-point threshold.

## Aggregate

| Metric | Claudex-loop | Codex-DeepSeek-loop |
|---|---:|---:|
| Quality score | 88.7 | 88.4 |
| Weighted defect recall | 100.0% | 100.0% |
| Seeded-defect precision | 63.9% | 56.5% |
| Verdict accuracy | 91.7% | 100.0% |
| Severity accuracy | 89.7% | 92.3% |
| Clean-control accuracy | 100.0% | 100.0% |
| Operational completion | 24/24 | 24/24 |
| Attempts (failed) | 24 (0) | 24 (0) |
| Median latency | 16.8s | 10.7s |
| Cost | $0.9780 CLI notional | $0.0399 to $0.0798 estimate |

Quality score = 50% severity-weighted recall + 25% seeded-defect precision + 15% verdict accuracy + 10% severity accuracy. Cost and speed stay separate; they cannot buy a quality win. Claude's CLI notional amount is not a subscription invoice; DeepSeek dollar figures are runner estimates from measured tokens.

## Interpretation

- Seeded defects found: Claudex 39/39; DeepSeek 39/39.
- Clean-control accuracy: Claudex 100.0%; DeepSeek 100.0%.
- Median effective latency: Claudex 16.8s; DeepSeek 10.7s.
- `BLOCKED` verdicts: Claudex 2; DeepSeek 0. Review each result's coverage and limitations before judging whether a block was warranted.
- First-attempt failures: Claudex 0; DeepSeek 0. Any retry time, tokens, and estimated cost remain included.

## Per run

| Job | System | TP | Unmatched | FN | Verdict | Missed |
|---|---|---:|---:|---:|---|---|
| plan-ledger-transfer-r2-deepseek | deepseek | 3 | 1 | 0 | REVISE | — |
| inspect-ledger-write-r2-claudex | claudex | 2 | 1 | 0 | REVISE | — |
| inspect-tenant-cache-r2-deepseek | deepseek | 1 | 3 | 0 | REVISE | — |
| plan-market-validation-r1-claudex | claudex | 2 | 0 | 0 | REVISE | — |
| inspect-clean-retry-r2-claudex | claudex | 0 | 0 | 0 | APPROVED | — |
| inspect-clean-retry-r1-claudex | claudex | 0 | 0 | 0 | APPROVED | — |
| inspect-tenant-cache-r3-deepseek | deepseek | 1 | 4 | 0 | REVISE | — |
| plan-ledger-transfer-r3-claudex | claudex | 3 | 0 | 0 | REVISE | — |
| inspect-tenant-cache-r3-claudex | claudex | 1 | 2 | 0 | REVISE | — |
| inspect-ledger-write-r1-deepseek | deepseek | 2 | 0 | 0 | REVISE | — |
| inspect-zip-slip-r2-claudex | claudex | 1 | 1 | 0 | REVISE | — |
| inspect-ledger-write-r3-claudex | claudex | 2 | 1 | 0 | REVISE | — |
| inspect-clean-retry-r3-claudex | claudex | 0 | 0 | 0 | APPROVED | — |
| inspect-ledger-write-r2-deepseek | deepseek | 2 | 0 | 0 | REVISE | — |
| inspect-zip-slip-r3-claudex | claudex | 1 | 3 | 0 | REVISE | — |
| plan-market-validation-r1-deepseek | deepseek | 2 | 2 | 0 | REVISE | — |
| inspect-ledger-write-r1-claudex | claudex | 2 | 1 | 0 | REVISE | — |
| inspect-zip-slip-r1-deepseek | deepseek | 1 | 2 | 0 | REVISE | — |
| inspect-clean-retry-r1-deepseek | deepseek | 0 | 0 | 0 | APPROVED | — |
| inspect-tenant-cache-r1-deepseek | deepseek | 1 | 2 | 0 | REVISE | — |
| plan-archive-safety-r1-claudex | claudex | 3 | 0 | 0 | REVISE | — |
| inspect-receipt-parser-r3-deepseek | deepseek | 1 | 1 | 0 | REVISE | — |
| inspect-zip-slip-r1-claudex | claudex | 1 | 2 | 0 | REVISE | — |
| inspect-zip-slip-r3-deepseek | deepseek | 1 | 2 | 0 | REVISE | — |
| plan-archive-safety-r3-deepseek | deepseek | 3 | 1 | 0 | REVISE | — |
| plan-ledger-transfer-r1-deepseek | deepseek | 3 | 0 | 0 | REVISE | — |
| plan-market-validation-r3-claudex | claudex | 2 | 0 | 0 | REVISE | — |
| inspect-clean-retry-r2-deepseek | deepseek | 0 | 0 | 0 | APPROVED | — |
| plan-market-validation-r3-deepseek | deepseek | 2 | 2 | 0 | REVISE | — |
| plan-ledger-transfer-r2-claudex | claudex | 3 | 0 | 0 | REVISE | — |
| plan-market-validation-r2-claudex | claudex | 2 | 0 | 0 | BLOCKED | — |
| inspect-zip-slip-r2-deepseek | deepseek | 1 | 3 | 0 | REVISE | — |
| plan-archive-safety-r2-claudex | claudex | 3 | 0 | 0 | REVISE | — |
| plan-archive-safety-r1-deepseek | deepseek | 3 | 0 | 0 | REVISE | — |
| inspect-receipt-parser-r2-deepseek | deepseek | 1 | 2 | 0 | REVISE | — |
| inspect-clean-retry-r3-deepseek | deepseek | 0 | 0 | 0 | APPROVED | — |
| plan-archive-safety-r3-claudex | claudex | 3 | 0 | 0 | BLOCKED | — |
| plan-market-validation-r2-deepseek | deepseek | 2 | 4 | 0 | REVISE | — |
| inspect-receipt-parser-r1-claudex | claudex | 1 | 2 | 0 | REVISE | — |
| inspect-tenant-cache-r2-claudex | claudex | 1 | 3 | 0 | REVISE | — |
| inspect-receipt-parser-r2-claudex | claudex | 1 | 2 | 0 | REVISE | — |
| inspect-tenant-cache-r1-claudex | claudex | 1 | 2 | 0 | REVISE | — |
| inspect-receipt-parser-r1-deepseek | deepseek | 1 | 1 | 0 | REVISE | — |
| plan-ledger-transfer-r1-claudex | claudex | 3 | 0 | 0 | REVISE | — |
| inspect-receipt-parser-r3-claudex | claudex | 1 | 2 | 0 | REVISE | — |
| plan-archive-safety-r2-deepseek | deepseek | 3 | 0 | 0 | REVISE | — |
| plan-ledger-transfer-r3-deepseek | deepseek | 3 | 0 | 0 | REVISE | — |
| inspect-ledger-write-r3-deepseek | deepseek | 2 | 0 | 0 | REVISE | — |

## Limits

- Synthetic fixtures measure review stages, not builder creativity or full project delivery.
- Claudex gets native read-only repository access. DeepSeek gets the plan, diff, new files, and declared context. This is native-mode effectiveness, not identical transport.
- Unmatched findings count as false positives only against the seeded answer key. Review `SCORES.json` before publication because a reviewer may find a valid unseeded defect.
- Model, CLI, runner hashes, tokens, and cost labels belong with any quoted result. See `RUN-CONFIG.json`; results do not generalize beyond this suite and run configuration.
