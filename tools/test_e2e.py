#!/usr/bin/env python3
"""Comprehensive E2E test for Firefly Merge Web Tool.

Tests every button and interactive element using the test_data/ CSV files.

Usage:
  python tools/test_e2e.py
  python tools/test_e2e.py --base-url http://localhost:8080 --out-dir output_check/e2e
  python tools/test_e2e.py --headed   # run with visible browser

Requires:
  pip install playwright
  python -m playwright install chromium
"""

from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows to handle box-drawing chars
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


BASE_URL = "http://localhost:8080"
TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"
ING_CSV = TEST_DATA_DIR / "ing_export_jan2025.csv"
BUNQ_CSV = TEST_DATA_DIR / "bunq_export_jan2025.csv"

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

results: list[tuple[str, str, str]] = []  # (status, name, detail)


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))
    marker = {"PASS": "✓", "FAIL": "✗", "SKIP": "-"}.get(status, "?")
    print(f"  [{marker}] {name}" + (f": {detail}" if detail else ""))


def check(condition: bool, name: str, fail_detail: str = "") -> bool:
    record(PASS if condition else FAIL, name, "" if condition else fail_detail)
    return condition


def safe_click(page, selector: str, name: str, timeout_ms: int = 5000) -> bool:
    try:
        loc = page.locator(selector)
        if loc.count() == 0:
            record(FAIL, name, f"element not found: {selector}")
            return False
        el = loc.first
        # Skip disabled buttons rather than timing out
        try:
            disabled = el.evaluate("el => el.disabled || el.hasAttribute('disabled')")
            if disabled:
                record(SKIP, name, "element is disabled")
                return False
        except Exception:
            pass
        # Use JS scroll (works inside overflow containers too)
        try:
            el.evaluate("el => el.scrollIntoView({block: 'center', inline: 'nearest'})")
            page.wait_for_timeout(100)
        except Exception:
            pass
        el.click(timeout=timeout_ms)
        page.wait_for_timeout(200)
        record(PASS, name)
        return True
    except Exception as e:
        record(FAIL, name, str(e)[:120])
        return False


def close_picker(page) -> None:
    """Close the tcm column picker by clicking outside it."""
    picker = page.locator("#tcm-picker-panel")
    if picker.count() > 0 and picker.is_visible():
        # Click a neutral area — the page heading or body
        page.locator("body").click(position={"x": 10, "y": 10})
        page.wait_for_timeout(200)


def safe_fill(page, selector: str, value: str, name: str) -> bool:
    try:
        page.locator(selector).first.fill(value)
        record(PASS, name)
        return True
    except Exception as e:
        record(FAIL, name, str(e)[:120])
        return False


def wait_for_text(page, selector: str, text: str, timeout_ms: int = 15000) -> bool:
    try:
        page.wait_for_function(
            f"document.querySelector('{selector}')?.textContent?.includes('{text}')",
            timeout=timeout_ms,
        )
        return True
    except Exception:
        return False


def screenshot(page, out_dir: Path, name: str) -> None:
    path = out_dir / f"{name}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Section helpers
# ---------------------------------------------------------------------------

def switch_subtab(page, tab_key: str) -> None:
    page.locator(f'button.subtab-btn[data-sub-tab="{tab_key}"]').first.click()
    page.wait_for_timeout(300)


def switch_main_tab(page, tab_key: str) -> None:
    page.locator(f'button.main-top-tab[data-main-tab="{tab_key}"]').first.click()
    page.wait_for_timeout(300)


# ---------------------------------------------------------------------------
# Test: Config page
# ---------------------------------------------------------------------------

def test_config_page(page, out_dir: Path) -> None:
    print("\n── Config page ──")
    page.goto(f"{BASE_URL}/config", wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    screenshot(page, out_dir, "config_initial")

    # Nav links
    nav_links = page.locator("nav.topnav a, nav.topnav button").all()
    nav_texts = [el.text_content().strip() for el in nav_links]
    check("Configuration" in nav_texts, "nav: Configuration link active")

    # Check for stale Ollama nav link (should NOT be present - it goes to /#ollama
    # which has no corresponding section on the index page)
    ollama_nav = page.locator('nav.topnav a[href="/#ollama"]')
    if ollama_nav.count() > 0:
        record(FAIL, "nav config: stale Ollama link present", "href='/#ollama' has no target section")
    else:
        record(PASS, "nav config: no stale Ollama link")

    # Config sections: expand all <details>
    for summary_text in ["Firefly-III", "Firefly CSV Importer", "Merge Parsing", "Ollama", "Import / Export"]:
        loc = page.locator(f"details.config-group summary").filter(has_text=summary_text)
        if loc.count() > 0:
            details = loc.locator("xpath=..").first
            is_open = details.evaluate("el => el.open")
            if not is_open:
                loc.first.click()
                page.wait_for_timeout(150)
            record(PASS, f"config section visible: {summary_text}")
        else:
            record(FAIL, f"config section missing: {summary_text}")

    # Form fields visible
    for field_id, label in [
        ("firefly_url", "Firefly URL"),
        ("firefly_secret", "Firefly Secret"),
        ("firefly_token", "Firefly Token"),
        ("firefly_timeout", "Firefly Timeout"),
        ("firefly_batch_size", "Batch Size"),
        ("ollama_url", "Ollama URL"),
        ("ollama_model", "Ollama Model"),
        ("ollama_categories", "Ollama Categories"),
        ("ollama_prompt_template", "Ollama Prompt Template"),
    ]:
        check(
            page.locator(f"#{field_id}").count() > 0,
            f"config field present: {label}",
        )

    screenshot(page, out_dir, "config_expanded")

    # Save Configuration
    safe_click(page, "#save-config", "config: Save Configuration button")
    page.wait_for_timeout(500)
    screenshot(page, out_dir, "config_after_save")

    # Export YAML
    try:
        with page.expect_download(timeout=6000) as dl_info:
            page.locator("#export-config-yaml").scroll_into_view_if_needed()
            page.locator("#export-config-yaml").click()
        dl = dl_info.value
        check(dl.suggested_filename.endswith(".yml") or dl.suggested_filename.endswith(".yaml"),
              "config: YAML download has .yml extension", dl.suggested_filename)
        record(PASS, "config: Export YAML button")
    except Exception as e:
        record(FAIL, "config: Export YAML", str(e)[:120])

    # Export JSON
    try:
        with page.expect_download(timeout=6000) as dl_info:
            page.locator("#export-config-json").scroll_into_view_if_needed()
            page.locator("#export-config-json").click()
        dl = dl_info.value
        check(dl.suggested_filename.endswith(".json"),
              "config: JSON download has .json extension", dl.suggested_filename)
        record(PASS, "config: Export JSON button")
    except Exception as e:
        record(FAIL, "config: Export JSON", str(e)[:120])

    # Upload Importer JSON button (file not set, expect error/warning not crash)
    safe_click(page, "#upload-importer-json-btn", "config: Upload Importer JSON button (no file)")
    page.wait_for_timeout(300)

    # Verify Importer JSON button
    safe_click(page, "#verify-importer-json-btn", "config: Verify Importer JSON button")
    page.wait_for_timeout(300)

    # Import Config button (no file, expect graceful handling)
    safe_click(page, "#import-config-btn", "config: Import Config button (no file)")
    page.wait_for_timeout(300)

    # Write Config button
    safe_click(page, "#write-config-file-btn", "config: Write Config File button")
    page.wait_for_timeout(500)
    screenshot(page, out_dir, "config_after_write")

    # Danger zone: open then cancel
    danger_summary = page.locator("details.danger-zone summary")
    if danger_summary.count() > 0:
        danger_details = danger_summary.locator("xpath=..").first
        is_open = danger_details.evaluate("el => el.open")
        if not is_open:
            danger_summary.first.click()
            page.wait_for_timeout(150)
        record(PASS, "config: Danger Zone section expandable")
        # Click Reset but cancel the confirm dialog
        page.on("dialog", lambda d: d.dismiss())
        safe_click(page, "#reset-config-btn", "config: Reset All Settings button visible")
        page.wait_for_timeout(300)
        # If there's a custom confirm modal instead:
        cancel_btn = page.locator("#confirm-modal-cancel")
        if cancel_btn.is_visible():
            cancel_btn.click()
            record(PASS, "config: Reset confirm modal: Cancel works")
        screenshot(page, out_dir, "config_danger_zone")


# ---------------------------------------------------------------------------
# Test: Merge form
# ---------------------------------------------------------------------------

def test_merge_form(page, out_dir: Path) -> str | None:
    """Upload test files and start a merge. Returns job_id or None."""
    print("\n── Merge form ──")
    page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
    page.wait_for_timeout(500)

    # Main tab visible
    check(
        page.locator('button.main-top-tab[data-main-tab="merge-workspace"]').count() > 0,
        "main: Merge tab button present",
    )

    # Subtab buttons all present
    for key, label in [
        ("merge-form-panel", "Merge"),
        ("job-panel", "Job Status"),
        ("duplicates-panel", "Duplicate Review"),
        ("transactions-panel", "Transactions"),
        ("ollama-panel", "Ollama"),
        ("analytics-panel", "Balances"),
        ("export-panel", "Export"),
    ]:
        check(
            page.locator(f'button.subtab-btn[data-sub-tab="{key}"]').count() > 0,
            f"subtab button present: {label}",
        )

    # Workflow stepper steps present
    for step in ["merge", "review", "categorise", "verify", "export"]:
        check(
            page.locator(f'button.stepper-step[data-stepper-step="{step}"]').count() > 0,
            f"stepper step present: {step}",
        )

    # Active job controls
    for btn_id, label in [
        ("#open-latest-job", "Open Latest"),
        ("#clear-active-job", "Clear"),
        ("#jump-history-btn", "History"),
    ]:
        check(page.locator(btn_id).count() > 0, f"active job control present: {label}")

    screenshot(page, out_dir, "merge_form_initial")

    # Verify merge form panel is default-visible
    merge_panel = page.locator("#merge-form-panel")
    check(merge_panel.is_visible(), "merge-form-panel: visible by default")

    # Submit button visible in merge panel
    submit_btn = page.locator("#submit")
    check(submit_btn.is_visible(), "merge form: Start Merge Job button visible")

    # Advanced options toggle
    adv = page.locator("details.advanced-options")
    if adv.count() > 0:
        adv.locator("summary").first.click()
        page.wait_for_timeout(150)
        check(adv.evaluate("el => el.open"), "merge form: Advanced Options expands")
        # Collapse again
        adv.locator("summary").first.click()
        page.wait_for_timeout(150)
        record(PASS, "merge form: Advanced Options collapses")

    # Check merge button NOT visible on other subtabs (reported issue)
    for tab_key, label in [
        ("job-panel", "Job Status"),
        ("duplicates-panel", "Duplicate Review"),
        ("transactions-panel", "Transactions"),
        ("ollama-panel", "Ollama"),
        ("analytics-panel", "Balances"),
        ("export-panel", "Export"),
    ]:
        switch_subtab(page, tab_key)
        page.wait_for_timeout(100)
        btn_visible = page.locator("#submit").is_visible()
        check(not btn_visible, f"Start Merge button hidden on {label} subtab",
              "Merge button visible when it should be hidden" if btn_visible else "")
        screenshot(page, out_dir, f"subtab_{tab_key.replace('-panel', '')}")

    # Switch back to merge form
    switch_subtab(page, "merge-form-panel")
    page.wait_for_timeout(200)

    # Upload test files
    if not ING_CSV.exists() or not BUNQ_CSV.exists():
        record(SKIP, "merge: file upload", f"Test data not found at {TEST_DATA_DIR}")
        return None

    page.locator("#files").set_input_files([str(ING_CSV), str(BUNQ_CSV)])
    page.wait_for_timeout(300)
    hint_text = page.locator("#files-selected-hint").text_content()
    check(
        hint_text and "No files" not in hint_text,
        "merge form: files-selected hint updates after file pick",
        hint_text or "(empty)",
    )
    screenshot(page, out_dir, "merge_form_files_selected")

    # Submit the merge job
    page.locator("#submit").click()
    page.wait_for_timeout(500)
    screenshot(page, out_dir, "merge_form_submitted")
    record(PASS, "merge form: Start Merge Job clicked")

    # Wait for job to appear in active-job-select or job-id field
    # The page should auto-switch to job status panel
    job_appeared = False
    for _ in range(30):
        job_id_el = page.locator("#job-id")
        if job_id_el.count() > 0:
            txt = job_id_el.text_content().strip()
            if txt:
                job_appeared = True
                break
        # also check active-job-select
        sel = page.locator("#active-job-select")
        if sel.count() > 0:
            val = sel.evaluate("el => el.value")
            if val:
                job_appeared = True
                break
        time.sleep(0.5)

    check(job_appeared, "merge: job created and ID visible")

    # Wait for merge to complete (status = done/error)
    job_done = False
    for _ in range(60):
        status_el = page.locator("#job-status")
        if status_el.count() > 0:
            status = status_el.text_content().strip().lower()
            if status in ("done", "error", "completed", "failed"):
                job_done = True
                check("error" not in status and "failed" not in status,
                      f"merge: job completed successfully (status={status})",
                      f"Job ended with status: {status}")
                break
        time.sleep(1)

    if not job_done:
        record(FAIL, "merge: job completion timeout", "Still not done after 60s")

    screenshot(page, out_dir, "merge_job_done")

    # Read back job id
    job_id = None
    sel = page.locator("#active-job-select")
    if sel.count() > 0:
        job_id = sel.evaluate("el => el.value")
    if not job_id:
        job_id_el = page.locator("#job-id")
        if job_id_el.count() > 0:
            job_id = job_id_el.text_content().strip()

    return job_id


# ---------------------------------------------------------------------------
# Test: Job Status subtab
# ---------------------------------------------------------------------------

def test_job_status(page, out_dir: Path) -> None:
    print("\n── Job Status subtab ──")
    switch_subtab(page, "job-panel")
    page.wait_for_timeout(300)

    check(page.locator("#job-id").count() > 0, "job status: job-id element present")
    check(page.locator("#job-status").count() > 0, "job status: status element present")
    check(page.locator("#logs").count() > 0, "job status: logs element present")
    logs_text = page.locator("#logs").text_content()
    check(bool(logs_text and logs_text.strip()), "job status: logs not empty")
    screenshot(page, out_dir, "job_status")


# ---------------------------------------------------------------------------
# Test: Duplicate Review subtab
# ---------------------------------------------------------------------------

def test_duplicate_review(page, out_dir: Path) -> None:
    print("\n── Duplicate Review subtab ──")
    switch_subtab(page, "duplicates-panel")
    page.wait_for_timeout(500)
    screenshot(page, out_dir, "dup_review_initial")

    # Search field
    safe_fill(page, "#dup-search", "groceries", "dup review: type in search field")
    safe_click(page, "#apply-dup-filters", "dup review: Apply filter button")
    page.wait_for_timeout(400)
    screenshot(page, out_dir, "dup_review_filtered")

    # Clear search
    safe_fill(page, "#dup-search", "", "dup review: clear search field")
    safe_click(page, "#apply-dup-filters", "dup review: Apply (clear) filter")
    page.wait_for_timeout(400)

    # Sort controls
    safe_click(page, "#dup-sort-by", "dup review: sort-by dropdown click")
    page.select_option("#dup-sort-by", "amount")
    safe_click(page, "#apply-dup-filters", "dup review: Apply sort by amount")
    page.wait_for_timeout(300)

    page.select_option("#dup-sort-dir", "desc")
    safe_click(page, "#apply-dup-filters", "dup review: Apply sort descending")
    page.wait_for_timeout(300)
    screenshot(page, out_dir, "dup_review_sorted")

    # Refresh button
    safe_click(page, "#refresh-dup-review", "dup review: Refresh button")
    page.wait_for_timeout(400)

    # Column picker
    safe_click(page, "#dup-columns-btn", "dup review: ⚙ Columns button")
    page.wait_for_timeout(300)
    col_picker = page.locator("#tcm-picker-panel")
    check(col_picker.count() > 0, "dup review: column picker opens", "picker element not found")
    screenshot(page, out_dir, "dup_review_col_picker")
    close_picker(page)

    # Select visible checkbox
    safe_click(page, "#select-visible-dup", "dup review: Select Visible button")
    page.wait_for_timeout(200)
    safe_click(page, "#clear-dup-selection", "dup review: Clear Selection button")
    page.wait_for_timeout(200)

    # Toggle all checkbox in header
    safe_click(page, "#toggle-all-dup-visible", "dup review: toggle-all checkbox in header")
    page.wait_for_timeout(200)

    # Restore selected (may show confirm modal if rows are checked)
    safe_click(page, "#restore-dup-selected", "dup review: Restore Selected button")
    page.wait_for_timeout(300)
    # Handle potential confirm modal
    if page.locator("#confirm-modal").is_visible():
        safe_click(page, "#confirm-modal-cancel", "dup review: Restore confirm modal → Cancel")

    # Page size change
    page.select_option("#dup-page-size", "10")
    page.wait_for_timeout(200)
    record(PASS, "dup review: page size changed to 10")

    # Pagination buttons (only click if enabled)
    for btn_id, label in [
        ("#dup-page-first", "first page"),
        ("#dup-page-prev", "prev page"),
        ("#dup-page-next", "next page"),
        ("#dup-page-last", "last page"),
    ]:
        safe_click(page, btn_id, f"dup review: pagination {label}")

    # Sortable column headers
    for col_selector, col_name in [
        ("th[data-sort-key='reason']", "Reason"),
        ("th[data-sort-key='amount']", "Amount"),
        ("th[data-sort-key='date']", "Date"),
    ]:
        th = page.locator(f"#duplicates-table {col_selector}")
        if th.count() > 0:
            th.first.click()
            page.wait_for_timeout(200)
            record(PASS, f"dup review: sort by column header {col_name}")

    # Confirm review button
    safe_click(page, "#confirm-dup-review", "dup review: Confirm Review button")
    page.wait_for_timeout(400)
    if page.locator("#confirm-modal").is_visible():
        safe_click(page, "#confirm-modal-ok", "dup review: Confirm Review modal → OK")
        page.wait_for_timeout(500)
    screenshot(page, out_dir, "dup_review_confirmed")


# ---------------------------------------------------------------------------
# Test: Transactions subtab
# ---------------------------------------------------------------------------

def test_transactions(page, out_dir: Path) -> None:
    print("\n── Transactions subtab ──")
    switch_subtab(page, "transactions-panel")
    page.wait_for_timeout(500)
    screenshot(page, out_dir, "transactions_initial")

    # Check table has rows
    rows = page.locator("#transactions-body tr")
    row_count = rows.count()
    check(row_count > 0, f"transactions: table has rows ({row_count})")

    # Search
    safe_fill(page, "#tx-search", "Albert", "transactions: type in search field")
    safe_click(page, "#apply-tx-filters", "transactions: Apply filter")
    page.wait_for_timeout(400)
    screenshot(page, out_dir, "transactions_searched")

    safe_fill(page, "#tx-search", "", "transactions: clear search")
    safe_click(page, "#apply-tx-filters", "transactions: Apply (clear)")
    page.wait_for_timeout(300)

    # Decision filter
    page.select_option("#tx-decision-filter", "merged")
    safe_click(page, "#apply-tx-filters", "transactions: filter by merged only")
    page.wait_for_timeout(300)

    page.select_option("#tx-decision-filter", "dropped")
    safe_click(page, "#apply-tx-filters", "transactions: filter by dropped only")
    page.wait_for_timeout(300)

    page.select_option("#tx-decision-filter", "all")
    safe_click(page, "#apply-tx-filters", "transactions: filter all")
    page.wait_for_timeout(300)

    # Include-dropped checkbox
    safe_click(page, "#tx-include-dropped", "transactions: include-dropped checkbox toggle")
    page.wait_for_timeout(200)
    safe_click(page, "#tx-include-dropped", "transactions: include-dropped checkbox toggle back")
    page.wait_for_timeout(200)

    # Sort
    page.select_option("#tx-sort-by", "amount")
    page.select_option("#tx-sort-dir", "desc")
    safe_click(page, "#apply-tx-filters", "transactions: sort by amount descending")
    page.wait_for_timeout(300)
    screenshot(page, out_dir, "transactions_sorted_amount")

    # Sortable column headers
    for col_selector, col_name in [
        ("th[data-sort-key='date']", "Date"),
        ("th[data-sort-key='amount']", "Amount"),
        ("th[data-sort-key='category']", "Category"),
    ]:
        th = page.locator(f"#transactions-table {col_selector}")
        if th.count() > 0:
            th.first.click()
            page.wait_for_timeout(200)
            record(PASS, f"transactions: sort by column header {col_name}")

    # Select visible / clear selection
    safe_click(page, "#select-visible", "transactions: Select Visible button")
    page.wait_for_timeout(200)
    safe_click(page, "#clear-selection", "transactions: Clear Selection button")
    page.wait_for_timeout(200)

    # Toggle all in header
    safe_click(page, "#toggle-all-visible", "transactions: toggle-all header checkbox")
    page.wait_for_timeout(200)

    # Column picker
    safe_click(page, "#tx-columns-btn", "transactions: ⚙ Columns button")
    page.wait_for_timeout(300)
    screenshot(page, out_dir, "transactions_col_picker")
    close_picker(page)

    # Overwrite-category checkbox
    safe_click(page, "#overwrite-category", "transactions: Overwrite existing categories checkbox")
    page.wait_for_timeout(100)

    # Auto-export checkbox
    safe_click(page, "#auto-export-after-categorize", "transactions: Auto-export checkbox")
    page.wait_for_timeout(100)

    # Ensure no rows are selected before testing Ollama buttons (toggle-all may have selected all)
    safe_click(page, "#clear-selection", "transactions: clear selection before Ollama test")
    page.wait_for_timeout(200)

    # Categorize Selected (Ollama) - no rows selected, should show warning toast not crash
    safe_click(page, "#categorize-ollama", "transactions: Categorize Selected (Ollama) button")
    page.wait_for_timeout(400)

    # Categorize All (Ollama) - switches to Ollama panel immediately, then navigate back
    safe_click(page, "#categorize-all-ollama", "transactions: Categorize All (Ollama) button")
    page.wait_for_timeout(500)
    # App navigates to Ollama panel after submit; switch back to transactions to continue
    switch_subtab(page, "transactions-panel")
    page.wait_for_timeout(300)

    # Download Categorized CSV — uses window.open(_blank), blocked in headless.
    # Verify: button present+enabled, and the CSV endpoint returns valid content.
    btn = page.locator("#download-categorized-csv")
    check(btn.count() > 0, "transactions: Download Categorized CSV button present")
    if btn.count() > 0:
        disabled = btn.evaluate("el => el.disabled")
        check(not disabled, "transactions: Download Categorized CSV button enabled")
        # Verify the underlying endpoint is reachable by evaluating fetch() in the page
        try:
            job_id = page.evaluate("window.activeJobId || ''")
            if job_id:
                status_code = page.evaluate(f"""
                    fetch('/api/jobs/{job_id}/transactions/categorized.csv')
                      .then(r => r.status)
                """)
                check(status_code == 200,
                      "transactions: CSV endpoint returns 200",
                      f"status={status_code}")
            else:
                record(SKIP, "transactions: CSV endpoint check (no active job id in JS)")
        except Exception as e:
            record(FAIL, "transactions: CSV endpoint check", str(e)[:120])

    # Page size
    page.evaluate("window.scrollTo(0, 0)")
    page.select_option("#tx-page-size", "10")
    page.wait_for_timeout(200)
    record(PASS, "transactions: page size changed to 10")

    # Pagination
    for btn_id, label in [
        ("#tx-page-first", "first"),
        ("#tx-page-prev", "prev"),
        ("#tx-page-next", "next"),
        ("#tx-page-last", "last"),
    ]:
        safe_click(page, btn_id, f"transactions: pagination {label}")

    # Inline category edit: click first category cell
    cat_cells = page.locator("#transactions-body td[data-field='category'], #transactions-body .cell-category")
    if cat_cells.count() > 0:
        cat_cells.first.click()
        page.wait_for_timeout(200)
        # Check if an input appears for editing
        inline_input = page.locator("#transactions-body input[type='text'], #transactions-body input.category-edit")
        if inline_input.count() > 0:
            inline_input.first.fill("Test Category")
            page.keyboard.press("Enter")
            page.wait_for_timeout(300)
            record(PASS, "transactions: inline category edit")
        else:
            record(SKIP, "transactions: inline category edit (no input appeared)")
    else:
        record(SKIP, "transactions: inline category edit (no category cells found)")

    screenshot(page, out_dir, "transactions_final")


# ---------------------------------------------------------------------------
# Test: Ollama subtab
# ---------------------------------------------------------------------------

def test_ollama_panel(page, out_dir: Path) -> None:
    print("\n── Ollama subtab ──")
    switch_subtab(page, "ollama-panel")
    page.wait_for_timeout(400)
    screenshot(page, out_dir, "ollama_initial")

    # Filter / sort controls
    safe_fill(page, "#ollama-job-filter", "", "ollama: job filter input reachable")
    page.select_option("#ollama-status-group", "completed")
    page.wait_for_timeout(200)
    page.select_option("#ollama-status-group", "all")
    page.wait_for_timeout(200)
    record(PASS, "ollama: status group filter change")

    page.select_option("#ollama-sort-by", "status")
    page.select_option("#ollama-sort-dir", "desc")
    record(PASS, "ollama: sort controls changed")

    page.select_option("#ollama-page-size", "10")
    record(PASS, "ollama: page size changed")

    # Refresh
    safe_click(page, "#refresh-ollama-events", "ollama: Refresh button")
    page.wait_for_timeout(400)

    # Column picker
    safe_click(page, "#ollama-columns-btn", "ollama: ⚙ Columns button")
    page.wait_for_timeout(300)
    screenshot(page, out_dir, "ollama_col_picker")
    close_picker(page)

    # Pagination
    for btn_id, label in [
        ("#ollama-page-first", "first"),
        ("#ollama-page-next", "next"),
        ("#ollama-page-last", "last"),
    ]:
        safe_click(page, btn_id, f"ollama: pagination {label}")

    # Stop Queue (expect confirm or no-op if empty)
    safe_click(page, "#stop-ollama-queue", "ollama: Stop Queue button")
    page.wait_for_timeout(300)
    if page.locator("#confirm-modal").is_visible():
        safe_click(page, "#confirm-modal-cancel", "ollama: Stop Queue → Cancel")

    # Delete Queue (expect confirm)
    safe_click(page, "#delete-ollama-queue", "ollama: Delete Queue button")
    page.wait_for_timeout(300)
    if page.locator("#confirm-modal").is_visible():
        safe_click(page, "#confirm-modal-cancel", "ollama: Delete Queue → Cancel")

    screenshot(page, out_dir, "ollama_final")


# ---------------------------------------------------------------------------
# Test: Balances subtab
# ---------------------------------------------------------------------------

def test_balances(page, out_dir: Path) -> None:
    print("\n── Balances subtab ──")
    switch_subtab(page, "analytics-panel")
    page.wait_for_timeout(500)
    screenshot(page, out_dir, "balances_initial")

    svg = page.locator("#balance-chart")
    check(svg.count() > 0, "balances: SVG chart element present")

    legend = page.locator("#balance-legend")
    check(legend.count() > 0, "balances: legend element present")

    # Check chart has content (paths/lines drawn)
    paths = page.locator("#balance-chart path, #balance-chart polyline, #balance-chart line")
    check(paths.count() > 0, f"balances: chart has drawn elements ({paths.count()})")

    screenshot(page, out_dir, "balances_final")


# ---------------------------------------------------------------------------
# Test: Export subtab
# ---------------------------------------------------------------------------

def test_export_panel(page, out_dir: Path) -> None:
    print("\n── Export subtab ──")
    switch_subtab(page, "export-panel")
    page.wait_for_timeout(400)
    screenshot(page, out_dir, "export_initial")

    # Refresh
    safe_click(page, "#refresh-export-status", "export: Refresh button")
    page.wait_for_timeout(300)

    # Column picker (exports table)
    safe_click(page, "#exports-columns-btn", "export: ⚙ Columns button (exports table)")
    page.wait_for_timeout(300)
    screenshot(page, out_dir, "export_col_picker")
    close_picker(page)

    # Export events controls
    page.select_option("#export-events-status-group", "completed")
    page.wait_for_timeout(200)
    page.select_option("#export-events-status-group", "all")
    page.wait_for_timeout(200)
    record(PASS, "export: events status group filter change")

    page.select_option("#export-events-sort-by", "status")
    page.select_option("#export-events-sort-dir", "desc")
    page.select_option("#export-events-page-size", "10")
    record(PASS, "export: events sort + page size controls")

    safe_click(page, "#refresh-export-events", "export: Refresh Queue button")
    page.wait_for_timeout(300)

    safe_click(page, "#export-events-columns-btn", "export: ⚙ Columns button (events table)")
    page.wait_for_timeout(300)
    close_picker(page)

    # Events pagination
    for btn_id, label in [
        ("#export-events-page-first", "first"),
        ("#export-events-page-next", "next"),
        ("#export-events-page-last", "last"),
    ]:
        safe_click(page, btn_id, f"export: events pagination {label}")

    # Start Export button (will likely fail if Firefly not configured, but should not crash)
    safe_click(page, "#start-firefly-export", "export: Start Export button")
    page.wait_for_timeout(500)
    screenshot(page, out_dir, "export_after_start")

    # Stop Export Queue
    safe_click(page, "#stop-firefly-export", "export: Stop Export Queue button")
    page.wait_for_timeout(300)
    if page.locator("#confirm-modal").is_visible():
        safe_click(page, "#confirm-modal-cancel", "export: Stop → Cancel")

    # Delete Export Queues (expect confirm)
    safe_click(page, "#delete-firefly-export", "export: Delete Export Queues button")
    page.wait_for_timeout(300)
    if page.locator("#confirm-modal").is_visible():
        safe_click(page, "#confirm-modal-cancel", "export: Delete queues → Cancel")

    screenshot(page, out_dir, "export_final")


# ---------------------------------------------------------------------------
# Test: History tab
# ---------------------------------------------------------------------------

def test_history_tab(page, out_dir: Path) -> None:
    print("\n── History tab ──")
    switch_main_tab(page, "history-workspace")
    page.wait_for_timeout(400)
    screenshot(page, out_dir, "history_initial")

    check(page.locator("#history-table-tab").count() > 0, "history: table present")

    # Refresh
    safe_click(page, "#refresh-history-tab", "history: Refresh button")
    page.wait_for_timeout(400)

    # Column picker
    safe_click(page, "#history-columns-btn", "history: ⚙ Columns button")
    page.wait_for_timeout(300)
    screenshot(page, out_dir, "history_col_picker")
    close_picker(page)

    # Check table has rows
    rows = page.locator("#history-body-tab tr")
    row_count = rows.count()
    check(row_count > 0, f"history: table has job rows ({row_count})")

    # Sortable column headers
    for col_selector, col_name in [
        ("th[data-sort-key='id']", "Job ID"),
        ("th[data-sort-key='status']", "Status"),
        ("th[data-sort-key='created']", "Created"),
        ("th[data-sort-key='merged']", "Merged count"),
    ]:
        th = page.locator(f"#history-table-tab {col_selector}")
        if th.count() > 0:
            th.first.click()
            page.wait_for_timeout(200)
            record(PASS, f"history: sort by column header {col_name}")

    # Click "Open" on the first job row to load it
    open_btn = page.locator("#history-body-tab button, #history-body-tab a").filter(has_text="Open").first
    if open_btn.count() > 0:
        open_btn.click()
        page.wait_for_timeout(500)
        check(
            page.locator("#merge-workspace").is_visible(),
            "history: Open job switches to Merge workspace",
        )
        record(PASS, "history: Open job button works")
    else:
        record(SKIP, "history: Open job button (no Open button found in rows)")

    screenshot(page, out_dir, "history_final")


# ---------------------------------------------------------------------------
# Test: Active job controls
# ---------------------------------------------------------------------------

def test_active_job_controls(page, out_dir: Path) -> None:
    print("\n── Active job controls ──")
    switch_main_tab(page, "merge-workspace")
    page.wait_for_timeout(300)

    # Open Latest
    safe_click(page, "#open-latest-job", "active job: Open Latest button")
    page.wait_for_timeout(400)

    # History shortcut
    safe_click(page, "#jump-history-btn", "active job: History shortcut button")
    page.wait_for_timeout(300)
    check(page.locator("#history-workspace").is_visible(), "active job: History button switches to History tab")

    # Switch back and clear
    switch_main_tab(page, "merge-workspace")
    page.wait_for_timeout(200)
    safe_click(page, "#clear-active-job", "active job: Clear button")
    page.wait_for_timeout(300)
    sel_val = page.locator("#active-job-select").evaluate("el => el.value")
    check(not sel_val, "active job: Clear resets active job select to empty", sel_val)

    # Stepper clicks (navigate to each panel)
    for step, panel in [
        ("merge", "merge-form-panel"),
        ("review", "duplicates-panel"),
        ("categorise", "transactions-panel"),
        ("verify", "analytics-panel"),
        ("export", "export-panel"),
    ]:
        btn = page.locator(f'button.stepper-step[data-stepper-step="{step}"]')
        if btn.count() > 0:
            btn.first.click()
            page.wait_for_timeout(200)
            panel_visible = page.locator(f"#{panel}").is_visible()
            check(panel_visible, f"stepper: clicking {step} shows {panel}")

    screenshot(page, out_dir, "active_job_controls_final")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Comprehensive E2E test for Firefly Merge.")
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--out-dir", default="output_check/e2e")
    parser.add_argument("--headed", action="store_true", help="Run with visible browser")
    args = parser.parse_args(argv)

    global BASE_URL
    BASE_URL = args.base_url.rstrip("/")

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed. Run: pip install playwright && python -m playwright install chromium")
        return 2

    print(f"Base URL : {BASE_URL}")
    print(f"Test data: {TEST_DATA_DIR}")
    print(f"Out dir  : {out_dir}")
    print(f"ING CSV  : {ING_CSV} ({'found' if ING_CSV.exists() else 'MISSING'})")
    print(f"bunq CSV : {BUNQ_CSV} ({'found' if BUNQ_CSV.exists() else 'MISSING'})")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Capture console errors
        console_errors: list[str] = []
        page.on("console", lambda msg: console_errors.append(f"{msg.type}: {msg.text}") if msg.type == "error" else None)
        page.on("pageerror", lambda err: console_errors.append(f"PAGE ERROR: {err}"))

        try:
            test_config_page(page, out_dir)
            page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
            page.wait_for_timeout(500)

            job_id = test_merge_form(page, out_dir)
            if job_id:
                test_job_status(page, out_dir)
                test_duplicate_review(page, out_dir)
                test_transactions(page, out_dir)
                test_ollama_panel(page, out_dir)
                test_balances(page, out_dir)
                test_export_panel(page, out_dir)
                test_active_job_controls(page, out_dir)

            test_history_tab(page, out_dir)

        finally:
            context.close()
            browser.close()

    # Summary
    passed = sum(1 for s, _, _ in results if s == PASS)
    failed = sum(1 for s, _, _ in results if s == FAIL)
    skipped = sum(1 for s, _, _ in results if s == SKIP)
    total = len(results)

    print(f"\n{'═'*60}")
    print(f"RESULTS: {passed}/{total} passed  |  {failed} failed  |  {skipped} skipped")
    print(f"{'═'*60}")

    if failed:
        print("\nFAILURES:")
        for status, name, detail in results:
            if status == FAIL:
                print(f"  ✗ {name}" + (f"\n      {detail}" if detail else ""))

    if console_errors:
        print(f"\nBROWSER CONSOLE ERRORS ({len(console_errors)}):")
        for err in console_errors[:20]:
            print(f"  {err}")

    print(f"\nScreenshots saved to: {out_dir}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
