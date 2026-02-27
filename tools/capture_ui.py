#!/usr/bin/env python3
"""Capture deterministic screenshots of the Firefly Merge web UI.

Usage:
  python tools/capture_ui.py --base-url http://localhost:8080 --out-dir output_check/ui

Requires:
  pip install playwright
  python -m playwright install chromium
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Tuple


def _safe_click(page, selector: str, timeout_ms: int = 2000) -> bool:
    loc = page.locator(selector)
    if loc.count() == 0:
        return False
    try:
        loc.first.click(timeout=timeout_ms)
        page.wait_for_timeout(150)
        return True
    except Exception:
        return False


def _capture_merge_subtabs(page, out_dir: Path, prefix: str) -> None:
    subtabs = [
        ("merge-form-panel", "merge_form"),
        ("job-panel", "job_status"),
        ("duplicates-panel", "duplicate_review"),
        ("analytics-panel", "balances"),
        ("transactions-panel", "transactions"),
        ("ollama-panel", "ollama"),
        ("export-panel", "export"),
    ]
    for tab_key, label in subtabs:
        _safe_click(page, f'button.subtab-btn[data-sub-tab="{tab_key}"]')
        page.wait_for_timeout(250)
        page.screenshot(path=str(out_dir / f"{prefix}_{label}.png"), full_page=True)


def _capture_main_tabs(page, out_dir: Path, prefix: str) -> None:
    # Merge workspace and its sub-tabs
    _safe_click(page, 'button.main-top-tab[data-main-tab="merge-workspace"]')
    page.wait_for_timeout(200)
    _capture_merge_subtabs(page, out_dir, f"{prefix}_tab_merge")

    # History top tab
    _safe_click(page, 'button.main-top-tab[data-main-tab="history-workspace"]')
    page.wait_for_timeout(200)
    page.screenshot(path=str(out_dir / f"{prefix}_tab_history.png"), full_page=True)


def _capture_profile(context, base_url: str, out_dir: Path, profile_name: str) -> None:
    page = context.new_page()
    page.goto(f"{base_url}/", wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    _capture_main_tabs(page, out_dir, profile_name)

    page.goto(f"{base_url}/config", wait_until="domcontentloaded")
    page.wait_for_timeout(300)
    page.screenshot(path=str(out_dir / f"{profile_name}_tab_configuration.png"), full_page=True)
    page.close()


def _profiles() -> Iterable[Tuple[str, int, int]]:
    return [
        ("desktop", 1720, 1000),
        ("mobile", 390, 844),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture Firefly Merge web UI screenshots.")
    parser.add_argument("--base-url", default="http://localhost:8080", help="Base URL where app is running.")
    parser.add_argument("--out-dir", default="output_check/ui", help="Directory where screenshots are written.")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("Playwright is required. Install with:", file=sys.stderr)
        print("  pip install playwright", file=sys.stderr)
        print("  python -m playwright install chromium", file=sys.stderr)
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for name, width, height in _profiles():
            context = browser.new_context(viewport={"width": width, "height": height})
            try:
                _capture_profile(context, args.base_url, out_dir, name)
            finally:
                context.close()
        browser.close()

    print(f"Saved screenshots to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
