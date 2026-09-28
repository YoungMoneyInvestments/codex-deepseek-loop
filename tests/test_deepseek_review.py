#!/usr/bin/env python3
"""Contract tests for the DeepSeek reviewer adapter.

Standard library only. No network access and no model quota: the DeepSeek API is
replaced by a local HTTP server replaying scripted responses, and Git fixtures are
disposable temporary repositories.
"""
from __future__ import annotations

import contextlib
import http.server
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills" / "deepseek-loop" / "scripts" / "deepseek_review.py"

spec = importlib.util.spec_from_file_location("deepseek_review", RUNNER)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

GIT = os.environ.get("GIT") or shutil.which("git") or "git"
BASE_ENV = dict(os.environ, DEEPSEEK_API_KEY="test-key",
                DEEPSEEK_LOOP_RETRY_BACKOFF="0,0,0")


def git(repo, *args):
    env = dict(BASE_ENV, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    result = subprocess.run([GIT, *args], cwd=str(repo), capture_output=True, env=env)
    if result.returncode:
        raise AssertionError(result.stderr.decode("utf-8", errors="replace"))
    return result.stdout


def make_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    (repo / "app.py").write_text("print('v1')\n", encoding="utf-8")
    (repo / "PLAN.md").write_text("# Plan\n\nGoal: keep the printed value correct.\n\n"
                                  "Acceptance: app.py prints v2 after the change.\n", encoding="utf-8")
    (repo / "obsolete.txt").write_text("remove me\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "base")
    return repo


def review_object(verdict="REVISE", findings=None, coverage=None, limitations=None):
    if findings is None:
        findings = [{"id": "F1", "severity": "high", "path": "app.py",
                     "evidence": "app.py:1 prints the wrong value on empty input.",
                     "fix": "Guard the empty input case."}]
    if coverage is None:
        coverage = ["PLAN.md", "app.py"]
    if limitations is None:
        limitations = []
    return {"verdict": verdict, "summary": "Summary text.", "findings": findings,
            "coverage": coverage, "limitations": limitations}


def api_body(review=None, content=None, finish="stop", usage=None):
    if content is None:
        content = json.dumps(review if review is not None else review_object())
    return {
        "id": "chatcmpl-test", "object": "chat.completion", "model": "deepseek-flash",
        "choices": [{"index": 0, "finish_reason": finish,
                     "message": {"role": "assistant", "content": content,
                                 "reasoning_content": "reasoning..."}}],
        "usage": usage or {"prompt_tokens": 100000, "completion_tokens": 5000,
                           "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 100000},
    }


class FakeAPI:
    """Local HTTP server replaying a scripted list of (status, body) responses."""

    def __init__(self, script, on_request=None):
        self.script = list(script)
        self.requests = []
        self.on_request = on_request
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                outer.requests.append(json.loads(self.rfile.read(length).decode("utf-8")))
                if outer.on_request:
                    outer.on_request()
                status, payload = outer.next_response()
                data = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
                if isinstance(data, str):
                    data = data.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def next_response(self):
        if len(self.script) > 1:
            return self.script.pop(0)
        return self.script[0]

    @property
    def base_url(self):
        return "http://127.0.0.1:%d" % self.server.server_port

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def run_cli(argv, env=None):
    merged = {"DEEPSEEK_API_KEY": "test-key"}
    merged.update(env or {})
    old = {key: os.environ.get(key) for key in merged}
    os.environ.update(merged)
    try:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = mod.main(argv)
        return code, out.getvalue()
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class ReviewModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dsl-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = make_repo(self.tmp)
        self.artifacts = self.tmp / "artifacts"
        self.artifacts.mkdir()

    def latest_result(self):
        runs = sorted(self.artifacts.glob("deepseek-loop-*"))
        return json.loads((runs[-1] / "result.json").read_text(encoding="utf-8"))

    def latest_dir(self):
        runs = sorted(self.artifacts.glob("deepseek-loop-*"))
        return runs[-1]

    def test_roles_resolution(self):
        code, out = run_cli(["roles", "--host", "claude"])
        self.assertEqual(code, 0)
        roles = json.loads(out)
        self.assertEqual(roles["reviewer"], "deepseek")
        self.assertEqual(roles["host"], "claude")
        self.assertEqual(roles["model"], "deepseek-flash")
        code, out = run_cli(["roles", "--host", "codex"])
        self.assertEqual(json.loads(out)["builder"], "codex")

    def test_review_happy_path(self):
        with FakeAPI([(200, api_body())]) as api:
            code, _ = run_cli(["review", "--host", "claude", "--repo", str(self.repo),
                               "--base-url", api.base_url, "--artifacts", str(self.artifacts)])
        self.assertEqual(code, 0)
        record = self.latest_result()
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["review"]["verdict"], "REVISE")
        self.assertEqual(record["model_observed"], "deepseek-flash")
        self.assertEqual(record["plan_sha256"], mod.digest((self.repo / "PLAN.md").read_bytes()))
        cost = record["cost_usd"]
        self.assertEqual(cost["cache_miss_tokens"], 100000)
        self.assertAlmostEqual(cost["usd_peak"], 0.036, places=6)
        self.assertAlmostEqual(cost["usd_off_peak"], 0.018, places=6)
        prompt = (self.latest_dir() / "prompt.txt").read_text(encoding="utf-8")
        self.assertIn("PLAN SHA256", prompt)
        self.assertIn("keep the printed value correct", prompt)
        request = json.loads((self.latest_dir() / "request.json").read_text(encoding="utf-8"))
        self.assertEqual(request["response_format"], {"type": "json_object"})
        self.assertEqual(request["reasoning_effort"], "high")
        self.assertEqual(request["thinking"], {"type": "enabled"})
        self.assertEqual(api.requests[0]["model"], "deepseek-flash")

    def test_retry_on_503_then_success(self):
        with FakeAPI([(503, {"error": "busy"}), (200, api_body())]) as api:
            code, _ = run_cli(["review", "--host", "codex", "--repo", str(self.repo),
                               "--base-url", api.base_url, "--artifacts", str(self.artifacts)])
        self.assertEqual(code, 0)
        record = self.latest_result()
        self.assertEqual(record["api"]["attempts"], 2)
        self.assertEqual(len(api.requests), 2)

    def test_parse_retry_on_empty_then_success(self):
        first_usage = {"prompt_tokens": 10, "completion_tokens": 2,
                       "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 10}
        second_usage = {"prompt_tokens": 20, "completion_tokens": 3,
                        "prompt_cache_hit_tokens": 5, "prompt_cache_miss_tokens": 15}
        with FakeAPI([(200, api_body(content="", usage=first_usage)),
                      (200, api_body(usage=second_usage))]) as api:
            code, _ = run_cli(["review", "--host", "claude", "--repo", str(self.repo),
                               "--base-url", api.base_url, "--artifacts", str(self.artifacts)])
        self.assertEqual(code, 0)
        record = self.latest_result()
        self.assertEqual(record["api"]["parse_retries"], 1)
        self.assertEqual(len(api.requests), 2)
        self.assertEqual(record["usage"]["prompt_tokens"], 30)
        self.assertEqual(record["usage"]["completion_tokens"], 5)
        self.assertEqual(record["usage"]["prompt_cache_hit_tokens"], 5)
        self.assertEqual(record["usage"]["prompt_cache_miss_tokens"], 25)
        self.assertTrue((self.latest_dir() / "response-01.json").is_file())
        self.assertTrue((self.latest_dir() / "response-02.json").is_file())

    def test_fails_closed_on_bad_schema(self):
        bad = json.dumps({"verdict": "APPROVED", "summary": "x"})
        with FakeAPI([(200, api_body(content=bad))]) as api:
            code, _ = run_cli(["review", "--host", "claude", "--repo", str(self.repo),
                               "--base-url", api.base_url, "--artifacts", str(self.artifacts)])
        self.assertEqual(code, 1)
        record = self.latest_result()
        self.assertEqual(record["status"], "failed")
        self.assertIn("Review must contain exactly", record["error"])
        self.assertIsNone(record["review"])
        self.assertEqual(len(api.requests), 2)  # initial attempt + one parse retry

    def test_http_error_4xx_fails_immediately(self):
        with FakeAPI([(400, {"error": "bad request"})]) as api:
            code, _ = run_cli(["review", "--host", "claude", "--repo", str(self.repo),
                               "--base-url", api.base_url, "--artifacts", str(self.artifacts)])
        self.assertEqual(code, 1)
        self.assertEqual(len(api.requests), 1)

    def test_missing_api_key(self):
        env = {"DEEPSEEK_API_KEY": ""}
        code, _ = run_cli(["review", "--host", "claude", "--repo", str(self.repo),
                           "--artifacts", str(self.artifacts)], env=env)
        self.assertEqual(code, 1)

    def test_prompt_cap_enforced_before_call(self):
        with FakeAPI([(200, api_body())]) as api:
            code, _ = run_cli(["review", "--host", "claude", "--repo", str(self.repo),
                               "--base-url", api.base_url, "--artifacts", str(self.artifacts),
                               "--max-input-chars", "10"])
        self.assertEqual(code, 1)
        self.assertEqual(len(api.requests), 0)

    def test_artifacts_inside_checkout_refused(self):
        code, _ = run_cli(["review", "--host", "claude", "--repo", str(self.repo),
                           "--artifacts", str(self.repo / "runs")])
        self.assertEqual(code, 1)
        self.assertFalse((self.repo / "runs").exists())


class ValidationRuleTests(unittest.TestCase):
    def test_approved_with_material_finding_rejected(self):
        with self.assertRaises(mod.RunError):
            mod.validate_review(review_object(verdict="APPROVED"))

    def test_revise_without_findings_rejected(self):
        with self.assertRaises(mod.RunError):
            mod.validate_review(review_object(verdict="REVISE", findings=[]))

    def test_blocked_without_limitations_rejected(self):
        with self.assertRaises(mod.RunError):
            mod.validate_review(review_object(verdict="BLOCKED", findings=[]))

    def test_duplicate_finding_ids_rejected(self):
        finding = review_object()["findings"][0]
        with self.assertRaises(mod.RunError):
            mod.validate_review(review_object(findings=[finding, dict(finding)]))

    def test_zero_findings_approved_valid(self):
        value = mod.validate_review(review_object(verdict="APPROVED", findings=[]))
        self.assertEqual(value["verdict"], "APPROVED")

    def test_zero_findings_without_coverage_rejected(self):
        with self.assertRaises(mod.RunError):
            mod.validate_review(review_object(verdict="APPROVED", findings=[], coverage=[]))

    def test_severity_vocabulary_enforced(self):
        finding = dict(review_object()["findings"][0], severity="critical")
        with self.assertRaises(mod.RunError):
            mod.validate_review(review_object(findings=[finding]))

    def test_estimate_cost_handles_missing_usage(self):
        self.assertIsNone(mod.estimate_cost("deepseek-flash", None))
        self.assertIsNone(mod.estimate_cost("deepseek-flash", {}))


class ApprovalBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dsl-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = make_repo(self.tmp)
        self.artifacts = self.tmp / "artifacts"
        self.artifacts.mkdir()

    def latest_result_path(self):
        runs = sorted(self.artifacts.glob("deepseek-loop-*"))
        return runs[-1] / "result.json"

    def test_check_binding(self):
        approved = review_object(verdict="APPROVED", findings=[],
                                 coverage=["PLAN.md", "app.py"], limitations=[])
        with FakeAPI([(200, api_body(review=approved))]) as api:
            code, _ = run_cli(["review", "--host", "claude", "--repo", str(self.repo),
                               "--base-url", api.base_url, "--artifacts", str(self.artifacts)])
        self.assertEqual(code, 0)
        result_path = self.latest_result_path()
        code, out = run_cli(["check", "--host", "claude", "--repo", str(self.repo),
                             "--approval", str(result_path)])
        self.assertEqual(code, 0)
        self.assertIn("Approval matches", out)
        # Plan changed after approval -> binding fails.
        (self.repo / "PLAN.md").write_text("# Plan v2 changed\n", encoding="utf-8")
        code, _ = run_cli(["check", "--host", "claude", "--repo", str(self.repo),
                           "--approval", str(result_path)])
        self.assertEqual(code, 1)

    def test_check_rejects_non_approved(self):
        with FakeAPI([(200, api_body())]) as api:
            code, _ = run_cli(["review", "--host", "claude", "--repo", str(self.repo),
                               "--base-url", api.base_url, "--artifacts", str(self.artifacts)])
        self.assertEqual(code, 0)
        code, _ = run_cli(["check", "--host", "claude", "--repo", str(self.repo),
                           "--approval", str(self.latest_result_path())])
        self.assertEqual(code, 1)


class SnapshotAndInspectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dsl-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = make_repo(self.tmp)
        self.artifacts = self.tmp / "artifacts"
        self.artifacts.mkdir()
        self.base = git(self.repo, "rev-parse", "HEAD").decode().strip()

    def latest_dir(self):
        runs = sorted(self.artifacts.glob("deepseek-loop-*"))
        return runs[-1]

    def latest_result(self):
        return json.loads((self.latest_dir() / "result.json").read_text(encoding="utf-8"))

    def test_snapshot_manifest_covers_modified_untracked_deleted(self):
        (self.repo / "app.py").write_text("print('v2')\n", encoding="utf-8")
        (self.repo / "extra.py").write_text("x = 1\n", encoding="utf-8")
        (self.repo / "obsolete.txt").unlink()
        snap = mod.snapshot(self.repo, self.base)
        kinds = {entry["path"]: entry["kind"] for entry in snap["files"]}
        self.assertEqual(kinds.get("app.py"), "file")
        self.assertEqual(kinds.get("extra.py"), "file")
        self.assertEqual(kinds.get("obsolete.txt"), "deleted")
        first = snap["sha256"]
        self.assertEqual(mod.snapshot(self.repo, self.base)["sha256"], first)

    def test_inspect_inlines_diff_and_new_files(self):
        (self.repo / "app.py").write_text("print('v2')\n", encoding="utf-8")
        (self.repo / "extra.py").write_text("VALUE = 42\n", encoding="utf-8")
        approved = review_object(verdict="APPROVED", findings=[],
                                 coverage=["PLAN.md", "app.py", "extra.py"], limitations=[])
        with FakeAPI([(200, api_body(review=approved))]) as api:
            code, _ = run_cli(["inspect", "--host", "claude", "--repo", str(self.repo),
                               "--base", self.base, "--base-url", api.base_url,
                               "--artifacts", str(self.artifacts)])
        self.assertEqual(code, 0)
        record = self.latest_result()
        self.assertEqual(record["base"], self.base)
        self.assertEqual(record["snapshot"]["files"][0]["kind"], "file")
        prompt = (self.latest_dir() / "prompt.txt").read_text(encoding="utf-8")
        self.assertIn("+print('v2')", prompt)
        self.assertIn("FILE: extra.py", prompt)
        self.assertIn("VALUE = 42", prompt)
        self.assertIn("TRACKED DIFF", prompt)

    def test_inspect_requires_base(self):
        code, _ = run_cli(["inspect", "--host", "claude", "--repo", str(self.repo),
                           "--artifacts", str(self.artifacts)])
        self.assertEqual(code, 1)

    def test_inspect_detects_code_change_during_run(self):
        def mutate():
            (self.repo / "app.py").write_text("print('mutated mid-run')\n", encoding="utf-8")

        approved = review_object(verdict="APPROVED", findings=[], coverage=["x"], limitations=[])
        with FakeAPI([(200, api_body(review=approved))], on_request=mutate) as api:
            code, _ = run_cli(["inspect", "--host", "claude", "--repo", str(self.repo),
                               "--base", self.base, "--base-url", api.base_url,
                               "--artifacts", str(self.artifacts)])
        self.assertEqual(code, 1)
        record = self.latest_result()
        self.assertEqual(record["status"], "failed")
        self.assertIn("Code changed during inspection", record["error"])


class CliProcessTests(unittest.TestCase):
    def test_roles_via_subprocess(self):
        env = dict(BASE_ENV)
        result = subprocess.run([sys.executable, str(RUNNER), "roles", "--host", "codex"],
                                capture_output=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn("deepseek", result.stdout.decode())

    def test_review_via_subprocess_exit_codes(self):
        tmp = Path(tempfile.mkdtemp(prefix="dsl-test-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        repo = make_repo(tmp)
        with FakeAPI([(200, api_body())]) as api:
            result = subprocess.run(
                [sys.executable, str(RUNNER), "review", "--host", "codex", "--repo", str(repo),
                 "--base-url", api.base_url, "--artifacts", str(tmp / "artifacts")],
                capture_output=True, env=BASE_ENV)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertIn('"status": "completed"', result.stdout.decode())


if __name__ == "__main__":
    unittest.main()
