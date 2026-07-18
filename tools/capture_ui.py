#!/usr/bin/env python3
"""Capture deterministic screenshots of the Firefly Merge web UI (MPA).

Usage:
  python tools/capture_ui.py --base-url http://localhost:8092 --out-dir output_check/ui
  python tools/capture_ui.py --base-url http://localhost:8092 --out-dir output_check/ui --job-id <id>

Requires:
  pip install playwright
  python -m playwright install chromium
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

# Pure resource-404 console errors are benign (e.g. a favicon or a job page
# fetched before any job exists) and should not fail the sweep. Page-level JS
# errors must still fail it.
_RESOURCE_404_RE = re.compile(r"Failed to load resource.*404", re.IGNORECASE)

PAGES: List[Tuple[str, str]] = [
    ("/", "merge"),
    ("/history", "jobs"),
    ("/config", "config"),
]

JOB_PAGES: List[Tuple[str, str]] = [
    ("", "status"),
    ("/review", "review"),
    ("/transactions", "transactions"),
    ("/balances", "balances"),
    ("/export", "export"),
]


def _profiles() -> Iterable[Tuple[str, int, int]]:
    return [
        ("desktop", 1720, 1000),
        ("mobile", 390, 844),
    ]


def _is_benign_console_error(text: str) -> bool:
    return bool(_RESOURCE_404_RE.search(text))


def _capture_profile(
    context,
    base_url: str,
    out_dir: Path,
    profile_name: str,
    pages: List[Tuple[str, str]],
    console_errors: List[str],
) -> None:
    page = context.new_page()

    def on_console(msg) -> None:
        if msg.type == "error" and not _is_benign_console_error(msg.text):
            console_errors.append(f"[{profile_name}] {page.url}: {msg.text}")

    page.on("console", on_console)

    for path, label in pages:
        page.goto(f"{base_url}{path}", wait_until="domcontentloaded")
        page.wait_for_timeout(400)
        page.screenshot(path=str(out_dir / f"{profile_name}_{label}.png"), full_page=True)

    page.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture Firefly Merge web UI screenshots.")
    parser.add_argument("--base-url", default="http://localhost:8080", help="Base URL where app is running.")
    parser.add_argument("--out-dir", default="output_check/ui", help="Directory where screenshots are written.")
    parser.add_argument("--job-id", default=None, help="If set, also capture the job detail pages for this job.")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    pages = list(PAGES)
    if args.job_id:
        pages += [(f"/jobs/{args.job_id}{sub}", label) for sub, label in JOB_PAGES]

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("Playwright is required. Install with:", file=sys.stderr)
        print("  pip install playwright", file=sys.stderr)
        print("  python -m playwright install chromium", file=sys.stderr)
        return 2

    console_errors: List[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for name, width, height in _profiles():
            context = browser.new_context(viewport={"width": width, "height": height})
            try:
                _capture_profile(context, args.base_url, out_dir, name, pages, console_errors)
            finally:
                context.close()
        browser.close()

    print(f"Saved screenshots to: {out_dir}")

    if console_errors:
        print("Console errors detected:", file=sys.stderr)
        for err in console_errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
