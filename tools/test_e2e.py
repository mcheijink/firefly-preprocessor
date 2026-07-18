#!/usr/bin/env python3
"""E2E flow test: merge -> review -> confirm -> categorize -> download.

Self-hosts uvicorn on a random port with a temp data dir. No browser,
no external services (Ollama/Firefly untouched).

Usage: python tools/test_e2e.py
Exit 0 on success, 1 on failure.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
TEST_DATA = ROOT / "test_data"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_health(base: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(f"{base}/api/health", timeout=2).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.3)
    raise RuntimeError("Server did not become healthy.")


def wait_job(base: str, job_id: str, timeout: float = 120.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = requests.get(f"{base}/api/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(1.0)
    raise RuntimeError("Merge job did not finish in time.")


def main() -> int:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    tmp = tempfile.mkdtemp(prefix="ff-e2e-")
    env = dict(os.environ, FIREFLY_WEB_DATA_DIR=tmp, APP_CONFIG_PATH=str(ROOT / "config.example.yml"))
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "firefly_web.app:app", "--port", str(port)],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    ok = False
    try:
        wait_health(base)

        # Pages render
        for path in ["/", "/history", "/config"]:
            r = requests.get(base + path)
            assert r.status_code == 200, f"{path} -> {r.status_code}"

        # Start merge
        files = [
            ("files", ("ing.csv", (TEST_DATA / "ing_export_jan2025.csv").read_bytes(), "text/csv")),
            ("files", ("bunq.csv", (TEST_DATA / "bunq_export_jan2025.csv").read_bytes(), "text/csv")),
        ]
        job_id = requests.post(f"{base}/api/jobs", files=files).json()["job_id"]
        job = wait_job(base, job_id)
        assert job["status"] == "completed", f"merge failed: {job.get('error')}"
        assert job["stats"]["merged_rows"] > 0

        # Job pages render
        for sub in ["", "/review", "/transactions", "/balances", "/export"]:
            r = requests.get(f"{base}/jobs/{job_id}{sub}")
            assert r.status_code == 200, f"/jobs/{job_id}{sub} -> {r.status_code}"

        # Summary endpoint
        summary = requests.get(f"{base}/api/jobs/{job_id}/summary").json()
        assert summary["total_rows"] == job["stats"]["merged_rows"]

        # Review flow
        review = summary["review"]
        if review["pending_duplicates"] > 0:
            r = requests.post(f"{base}/api/jobs/{job_id}/duplicates/review/confirm")
            assert r.status_code == 200
        assert requests.get(f"{base}/api/jobs/{job_id}/duplicates/review/status").json()["can_proceed"]

        # Default categorization + manual override
        r = requests.post(f"{base}/api/jobs/{job_id}/categorize/default", json={"overwrite": True})
        assert r.status_code == 200 and r.json()["updated"] >= 0
        r = requests.post(
            f"{base}/api/jobs/{job_id}/transactions/category",
            json={"merge_row_index": 1, "category": "E2ECheck"},
        )
        assert r.status_code == 200

        # Download categorized CSV, manual category present
        csv_text = requests.get(
            f"{base}/api/jobs/{job_id}/transactions/categorized.csv?include_uncategorized=true"
        ).text
        assert "E2ECheck" in csv_text

        # Deleted endpoints stay deleted
        assert requests.post(f"{base}/api/jobs/import").status_code in {404, 405}

        ok = True
        print("E2E OK")
        return 0
    finally:
        server.terminate()
        server.wait(timeout=10)
        output = server.stdout.read().decode("utf-8", errors="replace") if server.stdout else ""
        if not ok and output:
            lines = output.split("\n")
            last_lines = lines[-100:] if len(lines) > 100 else lines
            print("---- server log ----", file=sys.stderr)
            for line in last_lines:
                print(line, file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
