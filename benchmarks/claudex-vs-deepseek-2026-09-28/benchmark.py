#!/usr/bin/env python3
"""Run and score claudex-loop against codex-deepseek-loop reviewers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

from fixtures import CASES

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
DEFAULT_WORK = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "loop-benchmark"
DEFAULT_CLAUDEX = Path.home() / ".agents/skills/claudex-loop/scripts/runner.py"
DEFAULT_DEEPSEEK = Path.home() / "Projects/codex-deepseek-loop/skills/deepseek-loop/scripts/deepseek_review.py"
SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}


def run(command, *, cwd=None, env=None, timeout=30, check=True):
    return subprocess.run(
        [str(part) for part in command], cwd=cwd, env=env, timeout=timeout,
        capture_output=True, text=True, check=check,
    )


def git(repo, *args):
    return run(["git", *args], cwd=repo).stdout.strip()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def keychain_has_deepseek_key():
    account = os.environ.get("USER", "")
    try:
        result = run(
            ["/usr/bin/security", "find-generic-password", "-a", account,
             "-s", "codex-deepseek"],
            check=False,
        )
        return result.returncode == 0
    except OSError:
        return False


def git_head_for(path):
    try:
        result = run(["git", "-C", path.parent, "rev-parse", "HEAD"], check=False)
        return result.stdout.strip() or None
    except OSError:
        return None


def claude_auth_status():
    try:
        result = run(["claude", "auth", "status"], check=False)
        raw = json.loads(result.stdout)
        return {
            "logged_in": result.returncode == 0 and bool(raw.get("loggedIn")),
            "auth_method": raw.get("authMethod"),
            "api_provider": raw.get("apiProvider"),
            "subscription_type": raw.get("subscriptionType"),
        }
    except (OSError, json.JSONDecodeError):
        return {"logged_in": False, "auth_method": None,
                "api_provider": None, "subscription_type": None}


def version(command):
    try:
        result = run(command, check=False)
        return result.stdout.strip() or "unavailable"
    except OSError:
        return "unavailable"


def runtime_fingerprint(args):
    claude_auth = claude_auth_status()
    checks = {
        "python": sys.version.split()[0],
        "git": version(["git", "--version"]),
        "claude": version(["claude", "--version"]),
        "claude_logged_in": claude_auth["logged_in"],
        "claude_auth_method": claude_auth["auth_method"],
        "claude_api_provider": claude_auth["api_provider"],
        "claude_subscription_type": claude_auth["subscription_type"],
        "codex": version(["codex", "--version"]),
        "claudex_runner": str(args.claudex_runner),
        "claudex_runner_exists": args.claudex_runner.is_file(),
        "deepseek_runner": str(args.deepseek_runner),
        "deepseek_runner_exists": args.deepseek_runner.is_file(),
        "deepseek_key_env": bool(os.environ.get("DEEPSEEK_API_KEY")),
        "deepseek_key_keychain": keychain_has_deepseek_key(),
    }
    for label, path in (("claudex", args.claudex_runner), ("deepseek", args.deepseek_runner)):
        if path.is_file():
            checks[f"{label}_runner_sha256"] = sha256(path)
            checks[f"{label}_source_head"] = git_head_for(path)
    return checks


def deepseek_env():
    env = dict(os.environ)
    if env.get("DEEPSEEK_API_KEY"):
        return env
    account = env.get("USER", "")
    result = run(
        ["/usr/bin/security", "find-generic-password", "-a", account,
         "-s", "codex-deepseek", "-w"],
    )
    env["DEEPSEEK_API_KEY"] = result.stdout.strip()
    return env


def doctor(args):
    checks = runtime_fingerprint(args)
    print(json.dumps(checks, indent=2))
    return 0 if all((checks["claudex_runner_exists"], checks["deepseek_runner_exists"],
                     checks["claude"] != "unavailable", checks["claude_logged_in"],
                     checks["deepseek_key_env"] or checks["deepseek_key_keychain"])) else 1


def write_files(root, files):
    for relative, body in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


def prepare(args):
    root = args.work_dir.resolve()
    repos = root / "fixtures"
    if root.exists() and any(root.iterdir()):
        raise SystemExit(f"work directory is not empty: {root}")
    repos.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "seed": args.seed,
        "repetitions": args.repetitions,
        "created_at": time.time(),
        "fixture_catalog_sha256": sha256(HERE / "fixtures.py"),
        "runtime": runtime_fingerprint(args),
        "cases": [],
    }
    for case in CASES:
        repo = repos / case["id"]
        repo.mkdir()
        write_files(repo, case["base"])
        (repo / "PLAN.md").write_text(case["plan"], encoding="utf-8")
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "user.name", "Loop Benchmark")
        git(repo, "config", "user.email", "benchmark@invalid.local")
        git(repo, "add", ".")
        git(repo, "commit", "-q", "-m", "fixture baseline")
        base = git(repo, "rev-parse", "HEAD")
        write_files(repo, case["candidate"])
        manifest["cases"].append({
            "id": case["id"], "kind": case["kind"], "title": case["title"],
            "repo": str(repo), "base": base, "context": case["context"],
            "expected_count": len(case["expected"]),
        })
    jobs = [
        {"job_id": f"{case['id']}-r{rep}-{system}", "case_id": case["id"],
         "repetition": rep, "system": system}
        for rep in range(1, args.repetitions + 1)
        for case in CASES
        for system in ("claudex", "deepseek")
    ]
    random.Random(args.seed).shuffle(jobs)
    manifest["jobs"] = jobs
    (root / "suite.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"prepared {len(CASES)} cases and {len(jobs)} randomized jobs at {root}")
    return 0


def newest_result(artifact_root):
    results = sorted(artifact_root.glob("*/result.json"), key=lambda p: p.stat().st_mtime)
    if len(results) != 1:
        raise RuntimeError(f"expected one result.json below {artifact_root}, found {len(results)}")
    return results[0]


def command_for(args, job, case, repo, base, artifacts):
    common = ["--host", "codex", "--repo", repo, "--plan", "PLAN.md",
              "--artifacts", artifacts, "--timeout", str(args.timeout)]
    if job["system"] == "claudex":
        command = [sys.executable, args.claudex_runner, case["kind"], *common]
        if case["kind"] == "inspect":
            command += ["--base", base, "--builder", "codex",
                        "--builder-model", args.builder_model]
        return command
    command = [sys.executable, args.deepseek_runner, case["kind"], *common,
               "--model", "deepseek-flash", "--effort", "high",
               "--max-tokens", str(args.deepseek_max_tokens), "--retries", "0"]
    if case["kind"] == "inspect":
        command += ["--base", base]
    for path in case["context"]:
        command += ["--context", path]
    return command


def append_jsonl(path, record):
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_suite(args):
    root = args.work_dir.resolve()
    manifest = json.loads((root / "suite.json").read_text(encoding="utf-8"))
    case_by_id = {case["id"]: case for case in CASES}
    result_path = root / "results.jsonl"
    prior = []
    if result_path.exists():
        prior = [json.loads(line) for line in result_path.read_text(encoding="utf-8").splitlines() if line]
    done = {record["job_id"] for record in prior
            if not args.retry_failed or record.get("status") == "completed"}
    selected = {part.strip() for part in args.systems.split(",") if part.strip()}
    if not selected <= {"claudex", "deepseek"}:
        raise SystemExit("--systems must contain claudex, deepseek, or both")
    pending = [job for job in manifest["jobs"] if job["system"] in selected and job["job_id"] not in done]
    if not args.dry_run:
        runtime = runtime_fingerprint(args)
        if "claudex" in selected and not runtime["claude_logged_in"]:
            raise SystemExit("Claude CLI is not logged in. Run `claude /login`, then retry; no benchmark jobs were started.")
        if "deepseek" in selected and not (runtime["deepseek_key_env"] or runtime["deepseek_key_keychain"]):
            raise SystemExit("No DeepSeek key reference is available; no benchmark jobs were started.")
    if (not args.dry_run and any(job["system"] == "deepseek" for job in pending)
            and not args.allow_paid_deepseek):
        raise SystemExit("DeepSeek jobs are paid API calls. Re-run with --allow-paid-deepseek after approving the bounded spend.")
    deepseek_run_env = None
    if not args.dry_run and any(job["system"] == "deepseek" for job in pending):
        try:
            deepseek_run_env = deepseek_env()
        except (OSError, subprocess.CalledProcessError):
            raise SystemExit("DeepSeek key could not be read during preflight; no benchmark jobs were started.") from None
    if args.limit:
        pending = pending[:args.limit]
    print(f"running {len(pending)} jobs; prior completed={len(done)}")
    for index, job in enumerate(pending, 1):
        case = case_by_id[job["case_id"]]
        info = next(item for item in manifest["cases"] if item["id"] == job["case_id"])
        repo = info["repo"]
        attempt = 1 + sum(record["job_id"] == job["job_id"] for record in prior)
        artifact_root = root / "artifacts" / job["job_id"] / f"attempt-{attempt:02d}"
        command = command_for(args, job, case, repo, info["base"], artifact_root)
        if args.dry_run:
            print(json.dumps({"job": job["job_id"], "attempt": attempt,
                              "command": [str(x) for x in command]}))
            continue
        artifact_root.mkdir(parents=True, exist_ok=True)
        env = deepseek_run_env if job["system"] == "deepseek" else dict(os.environ)
        started = time.time()
        try:
            completed = run(command, cwd=repo, env=env, timeout=args.timeout + 60, check=False)
        except (subprocess.TimeoutExpired, OSError) as exc:
            record = {
                **job, "title": case["title"], "kind": case["kind"],
                "attempt": attempt, "status": "failed",
                "error": f"wrapper failure: {type(exc).__name__}: {exc}",
                "review": {}, "elapsed_seconds": round(time.time() - started, 2),
                "usage": None, "cost_usd": None, "requested_model": None,
                "observed_model": None, "source_result": None, "runner_exit": None,
                "command": [str(part) for part in command],
                "run_options": {"timeout": args.timeout,
                                "deepseek_max_tokens": args.deepseek_max_tokens,
                                "builder_model": args.builder_model},
            }
            append_jsonl(result_path, record)
            print(f"[{index}/{len(pending)}] {job['job_id']} status=failed error={record['error']}")
            continue
        wrapper = artifact_root / "wrapper"
        wrapper.mkdir(exist_ok=True)
        (wrapper / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (wrapper / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
        try:
            source_result = newest_result(artifact_root)
            raw = json.loads(source_result.read_text(encoding="utf-8"))
        except (RuntimeError, json.JSONDecodeError) as exc:
            source_result = None
            raw = {"status": "failed", "error": str(exc)}
        review = raw.get("review") if job["system"] == "deepseek" else raw.get("response")
        review = review if isinstance(review, dict) else {}
        usage = raw.get("usage")
        if usage is None:
            usage = review.get("metadata", {}).get("usage")
        cost = raw.get("cost_usd")
        if cost is None:
            cost = raw.get("total_cost_usd")
        if cost is None:
            cost = review.get("metadata", {}).get("total_cost_usd")
        api = raw.get("api")
        api = api if isinstance(api, dict) else {}
        record = {
            **job,
            "title": case["title"],
            "kind": case["kind"],
            "attempt": attempt,
            "status": raw.get("status", "failed"),
            "error": raw.get("error"),
            "review": review,
            "elapsed_seconds": raw.get("elapsed_seconds", round(time.time() - started, 2)),
            "usage": usage,
            "api": api,
            "cost_complete": not (
                job["system"] == "deepseek"
                and api.get("parse_retries", 0)
                and not api.get("usage_accumulated", False)
            ),
            "cost_usd": cost,
            "requested_model": raw.get("model_requested") or raw.get("requested_model"),
            "observed_model": raw.get("model_observed") or raw.get("observed_models") or (review or {}).get("metadata", {}).get("observed_models"),
            "source_result": str(source_result) if source_result else None,
            "runner_exit": completed.returncode,
            "command": [str(part) for part in command],
            "run_options": {"timeout": args.timeout,
                            "deepseek_max_tokens": args.deepseek_max_tokens,
                            "builder_model": args.builder_model},
        }
        append_jsonl(result_path, record)
        verdict = (review or {}).get("verdict", "-")
        print(f"[{index}/{len(pending)}] {job['job_id']} status={record['status']} verdict={verdict} elapsed={record['elapsed_seconds']}s")
    return 0


def finding_matches(finding, target):
    path = str(finding.get("path", "")).lower()
    if target["paths"] and not any(expected.lower() in path for expected in target["paths"]):
        return False
    text = " ".join(str(finding.get(key, "")) for key in ("path", "evidence", "fix", "summary")).lower()
    return all(any(keyword_matches(word, text) for word in group)
               for group in target["keywords"])


def keyword_matches(word, text):
    suffix = r"\w*" if word.isalnum() else ""
    return re.search(rf"(?<!\w){re.escape(word.lower())}{suffix}(?!\w)", text) is not None


def assign_matches(targets, findings):
    """Return a one-to-one target/finding assignment with stable best coverage."""
    candidates = {
        index: [item for item, finding in enumerate(findings)
                if finding_matches(finding, target)]
        for index, target in enumerate(targets)
    }
    order = sorted(range(len(targets)), key=lambda index: (len(candidates[index]), index))
    best_pairs: list[tuple[int, int]] = []
    best_count = -1

    def visit(position, used, chosen):
        nonlocal best_count
        if position == len(order):
            pairs = tuple(sorted(chosen))
            if len(pairs) > best_count:
                best_pairs.clear()
                best_pairs.extend(pairs)
                best_count = len(pairs)
            return
        target_index = order[position]
        for finding_index in sorted(candidates[target_index]):
            if finding_index not in used:
                visit(position + 1, used | {finding_index},
                      chosen + [(target_index, finding_index)])
        visit(position + 1, used, chosen)

    visit(0, set(), [])
    return [(targets[target_index], findings[finding_index])
            for target_index, finding_index in best_pairs]


def score_record(record, case):
    review = record.get("review") or {}
    findings = review.get("findings") if isinstance(review, dict) else []
    findings = findings if isinstance(findings, list) else []
    matches = assign_matches(case["expected"], findings)
    relevant = {id(finding) for _, finding in matches}
    expected_verdict = "REVISE" if case["expected"] else "APPROVED"
    completed = record.get("status") == "completed"
    target_weight = sum(SEVERITY_WEIGHT[item["severity"]] for item in case["expected"])
    hit_weight = sum(SEVERITY_WEIGHT[target["severity"]] for target, _ in matches)
    return {
        "job_id": record["job_id"], "system": record["system"], "case_id": case["id"],
        "completed": completed,
        "tp": len(matches), "fp": max(0, len(findings) - len(relevant)),
        "fn": len(case["expected"]) - len(matches),
        "target_weight": target_weight, "hit_weight": hit_weight,
        "severity_correct": sum(target["severity"] == str(finding.get("severity", "")).lower()
                                for target, finding in matches),
        "verdict_correct": completed and review.get("verdict") == expected_verdict,
        "verdict": review.get("verdict"),
        "matched": [target["id"] for target, _ in matches],
        "missed": [item["id"] for item in case["expected"] if item["id"] not in {target["id"] for target, _ in matches}],
        "unmatched_findings": [finding.get("id", f"finding-{index}") for index, finding in enumerate(findings) if id(finding) not in relevant],
        "elapsed_seconds": record.get("elapsed_seconds"),
        "usage": record.get("usage"), "cost_usd": record.get("cost_usd"),
    }


def safe_ratio(top, bottom):
    return top / bottom if bottom else 1.0


def token_counts(usage, system):
    if not isinstance(usage, dict):
        return {}
    if system == "claudex":
        return {
            "input_tokens": sum(int(usage.get(key) or 0) for key in
                                ("input_tokens", "cache_read_input_tokens",
                                 "cache_creation_input_tokens")),
            "output_tokens": int(usage.get("output_tokens") or 0),
        }
    return {
        "input_tokens": int(usage.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("completion_tokens") or 0),
    }


def deepseek_cost_from_usage(usage):
    if not isinstance(usage, dict):
        return None
    prompt = int(usage.get("prompt_tokens") or 0)
    hit = int(usage.get("prompt_cache_hit_tokens") or 0)
    if not hit:
        hit = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
    miss = int(usage.get("prompt_cache_miss_tokens") or max(0, prompt - hit))
    output = int(usage.get("completion_tokens") or 0)
    return {
        "usd_off_peak": (hit * 0.003 + miss * 0.15 + output * 0.60) / 1_000_000,
        "usd_peak": (hit * 0.006 + miss * 0.30 + output * 1.20) / 1_000_000,
    }


def aggregate(rows, records, history=None):
    history = history or records
    summary = {}
    for system in ("claudex", "deepseek"):
        selected = [row for row in rows if row["system"] == system]
        if not selected:
            summary[system] = {
                "jobs": 0, "completed": 0, "tp": 0, "fp": 0, "fn": 0,
                "precision": 0, "recall": 0, "weighted_recall": 0, "f1": 0,
                "severity_accuracy": 0, "verdict_accuracy": 0, "completion_rate": 0,
                "clean_control_accuracy": 0, "quality_score": 0,
                "attempts": 0, "failed_attempts": 0, "parse_retries": 0,
                "cost_complete": True,
                "median_latency_seconds": None, "tokens": {},
                "reported_cost_usd": None,
            }
            continue
        selected_ids = {row["job_id"] for row in selected}
        attempts = [record for record in history
                    if record["system"] == system and record["job_id"] in selected_ids]
        tp, fp, fn = (sum(row[key] for row in selected) for key in ("tp", "fp", "fn"))
        precision = safe_ratio(tp, tp + fp)
        recall = safe_ratio(tp, tp + fn)
        f1 = safe_ratio(2 * precision * recall, precision + recall)
        weighted_recall = safe_ratio(sum(row["hit_weight"] for row in selected),
                                     sum(row["target_weight"] for row in selected))
        severity = safe_ratio(sum(row["severity_correct"] for row in selected), tp)
        verdict = safe_ratio(sum(row["verdict_correct"] for row in selected), len(selected))
        completion = safe_ratio(sum(row["completed"] for row in selected), len(selected))
        clean = [row for row in selected if row["target_weight"] == 0]
        clean_accuracy = safe_ratio(sum(row["verdict_correct"] and row["fp"] == 0 for row in clean), len(clean))
        elapsed_by_job = {job_id: 0.0 for job_id in selected_ids}
        for attempt in attempts:
            if attempt.get("elapsed_seconds") is not None:
                elapsed_by_job[attempt["job_id"]] += float(attempt["elapsed_seconds"])
        latency = list(elapsed_by_job.values())
        token_totals = {}
        for attempt in attempts:
            for key, value in token_counts(attempt.get("usage"), system).items():
                token_totals[key] = token_totals.get(key, 0) + value
        costs = []
        for attempt in attempts:
            cost = attempt.get("cost_usd")
            if cost is None and system == "deepseek":
                cost = deepseek_cost_from_usage(attempt.get("usage"))
            costs.append(cost)
        numeric_costs = [float(cost) for cost in costs if isinstance(cost, (int, float))]
        estimated_low = sum(float(cost.get("usd_off_peak", cost.get("off_peak", 0)))
                            for cost in costs if isinstance(cost, dict))
        estimated_high = sum(float(cost.get("usd_peak", cost.get("peak", 0)))
                             for cost in costs if isinstance(cost, dict))
        reported_cost = None
        cost_complete = all(record.get("cost_complete", True) for record in attempts)
        parse_retries = sum(int((record.get("api") or {}).get("parse_retries", 0))
                            for record in attempts)
        if numeric_costs:
            kind = "cli_notional" if system == "claudex" else "provider_reported"
            reported_cost = {"kind": kind, "total": sum(numeric_costs)}
        elif estimated_low or estimated_high:
            reported_cost = {
                "kind": "runner_estimate" if cost_complete else "runner_estimate_lower_bound",
                "off_peak": estimated_low,
                "peak": estimated_high,
            }
        summary[system] = {
            "jobs": len(selected), "completed": sum(row["completed"] for row in selected),
            "tp": tp, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall, "weighted_recall": weighted_recall,
            "f1": f1, "severity_accuracy": severity, "verdict_accuracy": verdict,
            "completion_rate": completion, "clean_control_accuracy": clean_accuracy,
            "quality_score": 100 * (0.50 * weighted_recall + 0.25 * precision + 0.15 * verdict + 0.10 * severity),
            "attempts": len(attempts),
            "failed_attempts": sum(attempt.get("status") != "completed" for attempt in attempts),
            "parse_retries": parse_retries,
            "cost_complete": cost_complete,
            "median_latency_seconds": statistics.median(latency) if latency else None,
            "tokens": token_totals,
            "reported_cost_usd": reported_cost,
        }
    return summary


def score(args):
    root = args.work_dir.resolve()
    history = [json.loads(line) for line in (root / "results.jsonl").read_text(encoding="utf-8").splitlines() if line]
    first = {}
    for record in history:
        first.setdefault(record["job_id"], record)
    results = list(first.values())
    suite = json.loads((root / "suite.json").read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in CASES}
    rows = [score_record(record, cases[record["case_id"]]) for record in results]
    summary = aggregate(rows, results, history)
    expected_jobs = {system: sum(job["system"] == system for job in suite["jobs"])
                     for system in ("claudex", "deepseek")}
    output = {"schema_version": 1, "quality_formula": "50% weighted recall + 25% seeded precision + 15% verdict accuracy + 10% severity accuracy", "expected_jobs": expected_jobs, "summary": summary, "rows": rows}
    (root / "scores.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


def fmt_pct(value):
    return f"{100 * value:.1f}%"


def fmt_cost(value):
    cost = value["reported_cost_usd"]
    if not cost:
        return "n/a"
    if cost["kind"] == "cli_notional":
        return f"${cost['total']:.4f} CLI notional"
    if cost["kind"] == "provider_reported":
        return f"${cost['total']:.4f} provider reported"
    if cost["kind"] == "runner_estimate_lower_bound":
        return (f"at least ${cost['off_peak']:.4f} off-peak / "
                f"${cost['peak']:.4f} peak")
    return f"${cost['off_peak']:.4f} off-peak / ${cost['peak']:.4f} peak estimate"


def report(args):
    root = args.work_dir.resolve()
    scores = json.loads((root / "scores.json").read_text(encoding="utf-8"))
    summary = scores["summary"]
    a, b = summary["claudex"], summary["deepseek"]
    expected = scores["expected_jobs"]
    complete_suite = all(summary[system]["jobs"] == expected[system]
                         and summary[system]["completed"] == expected[system]
                         for system in ("claudex", "deepseek"))
    if not complete_suite:
        conclusion = "No head-to-head conclusion: full paired suite has not completed successfully."
    else:
        delta = a["quality_score"] - b["quality_score"]
        conclusion = ("Claudex-loop leads on preregistered quality score." if delta > 2 else
                      "Codex-DeepSeek-loop leads on preregistered quality score." if delta < -2 else
                      "Quality is a tie within the preregistered 2-point threshold.")
    lines = [
        "# Loop benchmark report", "", conclusion, "",
        "## Aggregate", "",
        "| Metric | Claudex-loop | Codex-DeepSeek-loop |", "|---|---:|---:|",
    ]
    metrics = [
        ("Quality score", lambda x: f"{x['quality_score']:.1f}"),
        ("Weighted defect recall", lambda x: fmt_pct(x["weighted_recall"])),
        ("Seeded-answer-key precision", lambda x: fmt_pct(x["precision"])),
        ("Verdict accuracy", lambda x: fmt_pct(x["verdict_accuracy"])),
        ("Severity accuracy", lambda x: fmt_pct(x["severity_accuracy"])),
        ("Clean-control accuracy", lambda x: fmt_pct(x["clean_control_accuracy"])),
        ("Operational completion", lambda x: f"{x['completed']}/{x['jobs']}"),
        ("Attempts (failed)", lambda x: f"{x['attempts']} ({x['failed_attempts']})"),
        ("Median latency", lambda x: f"{x['median_latency_seconds']:.1f}s" if x["median_latency_seconds"] is not None else "n/a"),
        ("Cost", fmt_cost),
    ]
    lines += [f"| {name} | {formatter(a)} | {formatter(b)} |" for name, formatter in metrics]
    lines += [
        "",
        "Quality score = 50% severity-weighted recall + 25% seeded-defect precision + 15% verdict accuracy + 10% severity accuracy. Cost and speed stay separate; they cannot buy a quality win. Claude's CLI notional amount is not a subscription invoice; DeepSeek dollar figures are runner estimates from measured tokens.",
        "",
        "## Interpretation",
        "",
    ]
    if complete_suite:
        blocked = {system: sum(row["system"] == system and row["verdict"] == "BLOCKED"
                               for row in scores["rows"])
                   for system in ("claudex", "deepseek")}
        lines += [
            f"- Seeded defects found: Claudex {a['tp']}/{a['tp'] + a['fn']}; DeepSeek {b['tp']}/{b['tp'] + b['fn']}.",
            f"- Clean-control accuracy: Claudex {fmt_pct(a['clean_control_accuracy'])}; DeepSeek {fmt_pct(b['clean_control_accuracy'])}.",
            f"- Median effective latency: Claudex {a['median_latency_seconds']:.1f}s; DeepSeek {b['median_latency_seconds']:.1f}s.",
            f"- `BLOCKED` verdicts: Claudex {blocked['claudex']}; DeepSeek {blocked['deepseek']}. Review each result's coverage and limitations before judging whether a block was warranted.",
            f"- Failed attempts across all recorded attempts: Claudex {a['failed_attempts']}; DeepSeek {b['failed_attempts']}. Any retry time, tokens, and estimated cost remain included.",
        ]
        if b["parse_retries"] and not b["cost_complete"]:
            lines.append(
                f"- DeepSeek JSON parse retries: {b['parse_retries']}. The live runner did not accumulate the first retry response's usage, so its token and cost totals are lower bounds.")
        elif b["parse_retries"]:
            lines.append(f"- DeepSeek JSON parse retries: {b['parse_retries']}; usage includes every response.")
    else:
        lines.append("- Full paired results are required before interpreting a winner.")
    lines += ["", "## Per run", "",
              "| Job | System | TP | Unmatched | FN | Verdict | Missed |",
              "|---|---|---:|---:|---:|---|---|"]
    for row in scores["rows"]:
        lines.append(f"| {row['job_id']} | {row['system']} | {row['tp']} | {row['fp']} | {row['fn']} | {row['verdict'] or 'failed'} | {', '.join(row['missed']) or '—'} |")
    lines += ["", "## Limits", "", "- Synthetic fixtures measure review stages, not builder creativity or full project delivery.", "- Claudex gets native read-only repository access. DeepSeek gets the plan, diff, new files, and declared context. This is native-mode effectiveness, not identical transport.", "- Matches use automated one-to-one keyword rules. Unmatched findings are not audited false positives; inspect `RESULTS.jsonl` and `SCORES.json` before making broader claims.", "- Model, CLI, runner hashes, tokens, and cost labels belong with any quoted result. See `RUN-CONFIG.json`; results do not generalize beyond this suite and run configuration.", ""]
    target = (args.output or root / "report.md").resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    print(target)
    return 0


def self_test(_args):
    records = []
    rows = []
    for case in CASES:
        assert case["kind"] in {"review", "inspect"}
        assert case["id"] and case["plan"] and case["base"]
        findings = []
        for target in case["expected"]:
            finding = {"id": target["id"], "path": target["paths"][0],
                       "evidence": " ".join(group[0] for group in target["keywords"]),
                       "fix": "fix", "severity": target["severity"]}
            assert finding_matches(finding, target), target["id"]
            findings.append(finding)
        for system in ("claudex", "deepseek"):
            fake = {"job_id": f"{case['id']}-{system}", "system": system,
                    "case_id": case["id"], "status": "completed", "elapsed_seconds": 1,
                    "review": {"verdict": "REVISE" if findings else "APPROVED",
                               "findings": findings}}
            records.append(fake)
            rows.append(score_record(fake, case))
    targets = {target["id"]: target for case in CASES for target in case["expected"]}
    assert not finding_matches(
        {"path": "PLAN.md", "evidence": "idempotency calculate", "fix": "none"},
        targets["idempotency-recorded-late"],
    )
    assert not finding_matches(
        {"path": "ledger.py", "evidence": "background worker", "fix": "none"},
        targets["binary-float-money"],
    )
    assert not finding_matches(
        {"path": "PLAN.md", "evidence": "No test for crash atomicity or concurrent retries."},
        targets["transfer-not-atomic"],
    )
    assert not finding_matches(
        {"path": "PLAN.md", "evidence": "No test for crash atomicity or concurrent retries."},
        targets["idempotency-recorded-late"],
    )
    broad = {
        "id": "broad", "path": "PLAN.md", "severity": "high",
        "evidence": ("A crash between sender debit and receiver credit breaks atomicity; "
                     "the idempotency key is stored after the balance update, so a "
                     "concurrent retry duplicates it."),
    }
    ledger_case = next(case for case in CASES if case["id"] == "plan-ledger-transfer")
    broad_row = score_record(
        {"job_id": "broad", "system": "claudex", "status": "completed",
         "review": {"verdict": "REVISE", "findings": [broad]}}, ledger_case)
    assert broad_row["tp"] == 1
    assert broad_row["fn"] == 2
    claude_usage = {
        "input_tokens": 2, "cache_read_input_tokens": 100,
        "cache_creation_input_tokens": 20, "output_tokens": 10,
        "iterations": [{"input_tokens": 2, "output_tokens": 9}],
    }
    assert token_counts(claude_usage, "claudex") == {
        "input_tokens": 122, "output_tokens": 10,
    }
    summary = aggregate(rows, records)
    assert summary["claudex"]["quality_score"] == 100
    assert summary["deepseek"]["quality_score"] == 100
    print(f"self-test passed: {len(CASES)} fixtures")
    return 0


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--work-dir", type=Path, default=DEFAULT_WORK)
    result.add_argument("--claudex-runner", type=Path, default=DEFAULT_CLAUDEX)
    result.add_argument("--deepseek-runner", type=Path, default=DEFAULT_DEEPSEEK)
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor").set_defaults(func=doctor)
    prep = sub.add_parser("prepare")
    prep.add_argument("--repetitions", type=int, default=3)
    prep.add_argument("--seed", type=int, default=20260928)
    prep.set_defaults(func=prepare)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--systems", default="claudex,deepseek")
    run_parser.add_argument("--allow-paid-deepseek", action="store_true")
    run_parser.add_argument("--deepseek-max-tokens", type=int, default=8192)
    run_parser.add_argument("--builder-model", default="gpt-5")
    run_parser.add_argument("--timeout", type=int, default=600)
    run_parser.add_argument("--limit", type=int)
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument("--retry-failed", action="store_true")
    run_parser.set_defaults(func=run_suite)
    sub.add_parser("score").set_defaults(func=score)
    report_parser = sub.add_parser("report")
    report_parser.add_argument("--output", type=Path)
    report_parser.set_defaults(func=report)
    sub.add_parser("self-test").set_defaults(func=self_test)
    return result


if __name__ == "__main__":
    arguments = parser().parse_args()
    raise SystemExit(arguments.func(arguments))
