# MPA Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Execution model:** Manager agent (Fable) dispatches one worker subagent (Sonnet) per task and reviews the diff between tasks. Workers follow steps literally; anything ambiguous goes back to the manager, workers must not improvise design decisions.

**Goal:** Convert the Firefly Merge web tool from a half-SPA into a multi-page app with job IDs in URLs, fix two data-race bugs, delete dead features, and apply the "reconciliation bench" visual design.

**Architecture:** FastAPI + Jinja2 serve one template per page (8 pages); all data stays API-driven with plain ES modules per page (`static/js/pages/*.js`) importing shared modules (`api.js`, `tables.js`, `polling.js`, `badge.js`, `stepper.js`). Background threads (merge, Ollama queue, Firefly export) are unchanged in architecture but fixed for concurrency correctness. Old SPA (`index.html`, monolithic `app.js`) is deleted at the end.

**Tech Stack:** Python 3.11+, FastAPI 0.117, Jinja2, vanilla ES modules, IBM Plex fonts (self-hosted), pytest, Playwright (local screenshots only), GitHub Actions.

## Global Constraints

- Branch: all work on `mpa-migration`, branched from the baseline commit created in Task 0. Nothing merges to `main` until the user has personally reviewed the UI on the dev server (port 8081).
- No CDN/external resources at runtime: fonts and all assets self-hosted under `firefly_web/static/`.
- All existing `/api/*` endpoints keep their paths and response shapes, EXCEPT deletions listed in Task 2 and the new `/api/jobs/{job_id}/summary` added in Task 5.
- Job history / DB contents are disposable: no schema migration code; dev server starts with a fresh empty DB.
- Design tokens (Task 7) are the only source of color/type values; no hard-coded colors in later tasks.
- UI copy rules: sentence case; buttons name the action ("Start merge", "Confirm review"); empty states are instructions, not moods; label "History" is replaced by "Jobs" everywhere.
- Python tests live in `tests/`, run with `pytest`. E2E script is `tools/test_e2e.py` (requests-based, self-hosts uvicorn, no browser). Screenshot tool is `tools/capture_ui.py` (Playwright, local use).
- Commit after every task with the message given in the task. Commit messages end with the standard Claude Code trailer.

---

### Task 0: Baseline commit and branch

**Files:** none created; git only.

- [ ] **Step 0.1:** From repo root on branch `claude/code-review-W3mqt`:

```bash
git add -A
git commit -m "WIP: pre-MPA baseline (uncommitted working tree as-is)"
git checkout -b mpa-migration
```

- [ ] **Step 0.2:** Verify: `git status` → clean tree, branch `mpa-migration`. `git log --oneline -1` shows the WIP commit.

---

### Task 1: Test scaffolding

**Files:**
- Modify: `requirements-dev.txt`
- Create: `tests/__init__.py` (empty), `tests/conftest.py`

**Interfaces:**
- Produces: pytest fixtures `tmp_settings` (Settings pointing at tmp dirs) and `tmp_store` (initialized JobStore) used by Tasks 3 and 4.

- [ ] **Step 1.1:** `requirements-dev.txt` becomes:

```
playwright==1.55.0
pytest==8.3.3
```

- [ ] **Step 1.2:** Create `tests/conftest.py`:

```python
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from firefly_web.settings import Settings
from firefly_web.store import JobStore


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "jobs").mkdir()
    config_path = tmp_path / "config.yml"
    config_path.write_text("own_accounts: []\n", encoding="utf-8")
    return Settings(
        base_dir=Path(__file__).resolve().parents[1],
        data_dir=data_dir,
        jobs_dir=data_dir / "jobs",
        db_path=data_dir / "app.db",
        default_config_path=config_path,
        config_dir=config_path.parent,
        app_secret="",
        max_upload_bytes=0,
    )


@pytest.fixture
def tmp_store(tmp_settings: Settings) -> JobStore:
    store = JobStore(tmp_settings.db_path)
    store.initialize()
    return store
```

- [ ] **Step 1.3:** Run `pip install -r requirements-dev.txt && python -m pytest tests/ -q` → "no tests ran" (exit 5 is fine).
- [ ] **Step 1.4:** Commit: `test: add pytest scaffolding with settings/store fixtures`

---

### Task 2: Delete dead features (cross-run dedupe, import-as-completed-job)

**Files:**
- Delete: `firefly_web/dedupe.py`
- Modify: `firefly_web/store.py`, `firefly_web/runner.py`, `firefly_web/app.py`
- Test: `tests/test_deletions.py`

**Interfaces:**
- Produces: `POST /api/jobs` no longer accepts/needs `dedupe_scope`; `/api/jobs/import` returns 404/405. Later tasks build UI without these.

- [ ] **Step 2.1:** Write failing test `tests/test_deletions.py`:

```python
import importlib


def test_dedupe_module_gone():
    found = importlib.util.find_spec("firefly_web.dedupe")
    assert found is None


def test_store_has_no_fingerprint_api(tmp_store):
    assert not hasattr(tmp_store, "lookup_fingerprint")
    assert not hasattr(tmp_store, "insert_fingerprint")


def test_fingerprints_table_not_created(tmp_store):
    import sqlite3
    with sqlite3.connect(tmp_store._db_path if hasattr(tmp_store, "_db_path") else tmp_store.db_path) as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "fingerprints" not in names
```

Note: check `firefly_web/store.py` for the actual attribute holding the db path (`self.db_path` or similar) and use that; adjust the test to the real name before running.

- [ ] **Step 2.2:** Run `python -m pytest tests/test_deletions.py -q` → FAIL.
- [ ] **Step 2.3:** Apply deletions:
  - Delete file `firefly_web/dedupe.py`.
  - `firefly_web/store.py`: remove methods `lookup_fingerprint` and `insert_fingerprint` (around lines 321–340) and the `CREATE TABLE IF NOT EXISTS fingerprints (...)` DDL block in `initialize()` (around line 39).
  - `firefly_web/runner.py`: remove `from .dedupe import apply_global_dedupe` (line 22), remove the whole method `_apply_global_dedupe` (lines 794–815), and in `_run_job` remove lines 165–171 (the `dedupe_scope` block including `global_duplicates_added`/`global_rows_inserted` variables); in the `stats` dict replace those two entries with literals `"global_duplicates_added": 0, "global_rows_inserted": 0` (keeps API shape stable).
  - `firefly_web/app.py`: in `create_job` remove the `dedupe_scope: str = Form(default="within_job")` parameter and the normalization/validation block (lines 253–257), and remove `"dedupe_scope": dedupe_scope` from `options`. Remove the entire `/api/jobs/import` endpoint `import_merged_job` (lines 319–395) and helpers `_normalize_imported_merged_rows` (lines 1332–1361) and `_normalize_imported_duplicates_rows` (lines 1364–1384). Keep `_write_rows_csv` only if still referenced — grep; if unreferenced, delete it too.
- [ ] **Step 2.4:** Verify no dangling references: `grep -rn "dedupe_scope\|apply_global_dedupe\|lookup_fingerprint\|insert_fingerprint\|import_merged_job\|_normalize_imported" firefly_web/ bank_merge_firefly.py` → only hits allowed: none. (Old `static/app.js` still references `importMergedJob`/dedupe scope — that file dies in Task 14; ignore it here.)
- [ ] **Step 2.5:** Run `python -m pytest tests/test_deletions.py -q` → PASS. Also `python -c "import firefly_web.app"` → no error.
- [ ] **Step 2.6:** Commit: `refactor: delete dead cross-run dedupe and import-as-completed-job`

---

### Task 3: Merge-safe Ollama category writes (race fix)

**Files:**
- Modify: `firefly_web/runner.py`
- Test: `tests/test_ollama_race.py`

**Interfaces:**
- Produces: `JobRunner._apply_categories_under_lock(job_id: str, merged_path: Path, assignments: Dict[int, str]) -> None`. `_run_ollama_categorization` no longer holds a full-CSV snapshot across writes and no longer does per-batch auto-export (auto-export handled in Task 4).

- [ ] **Step 3.1:** Write failing test `tests/test_ollama_race.py`:

```python
import csv
from pathlib import Path

from firefly_web.runner import JobRunner, _read_csv, _write_csv


FIELDS = ["date", "amount", "description", "category", "external_id"]


def _make_csv(path: Path, n: int) -> None:
    rows = [
        {"date": f"2025-01-{i+1:02d}", "amount": "1.00", "description": f"tx{i+1}", "category": "", "external_id": f"e{i+1}"}
        for i in range(n)
    ]
    _write_csv(path, rows, FIELDS)


def test_manual_edit_survives_ollama_run(tmp_settings, tmp_store, monkeypatch, tmp_path):
    merged = tmp_path / "merged.csv"
    _make_csv(merged, 4)
    runner = JobRunner(tmp_settings, tmp_store)
    tmp_store.create_job(job_id="job1", input_files=["a.csv"], options={})

    queued = []
    for idx in range(1, 5):
        event_id = tmp_store.create_ollama_event(
            job_id="job1", merge_row_index=idx, external_id=f"e{idx}",
            model="m", categories=["Groceries"], prompt="p",
            tx_date="", tx_amount="", tx_category="", tx_description="",
            tx_source_account="", tx_destination_account="", status="queued",
        )
        queued.append({"row_index": idx, "event_id": event_id})

    calls = {"n": 0}

    def fake_batch(rows, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            # Simulate a manual user edit landing on row 4 between batches.
            data, fields = _read_csv(merged)
            data[3]["category"] = "ManualPick"
            _write_csv(merged, data, fields)
        return {"categories": ["Groceries"] * len(rows), "row_ids": [], "prompt": "p", "response": "r"}

    monkeypatch.setattr("firefly_web.runner.categorize_ollama_batch_with_trace", fake_batch)

    runner._run_ollama_categorization(
        job_id="job1", merged_path=merged, queued_tasks=queued[:3],
        categories=["Groceries"], ollama_url="http://x", ollama_model="m",
        prompt_template="", temperature=0.0, timeout_seconds=5.0,
        batch_size=2, auto_export=False,
    )

    data, _ = _read_csv(merged)
    assert data[0]["category"] == "Groceries"
    assert data[1]["category"] == "Groceries"
    assert data[2]["category"] == "Groceries"
    assert data[3]["category"] == "ManualPick"  # manual edit must survive
```

Note: check the exact signature of `store.create_ollama_event` in `firefly_web/store.py` and adjust the call to match (it may take fewer/differently-named kwargs). Do not change the assertions.

- [ ] **Step 3.2:** Run `python -m pytest tests/test_ollama_race.py -q` → FAIL (row 4 clobbered back to "").
- [ ] **Step 3.3:** In `firefly_web/runner.py` add the helper method to `JobRunner`:

```python
    def _apply_categories_under_lock(self, job_id: str, merged_path: Path, assignments: Dict[int, str]) -> None:
        if not assignments:
            return
        with get_job_lock(job_id):
            rows, fieldnames = _read_csv(merged_path)
            for row_index, category in assignments.items():
                if 1 <= row_index <= len(rows):
                    rows[row_index - 1]["category"] = category
            _write_csv(merged_path, rows, fieldnames)
```

Then rework `_run_ollama_categorization`: the initial `rows, fieldnames = _read_csv(merged_path)` stays (used for prompts and range checks only). In the per-batch success block, build `batch_assignments: Dict[int, str]` mapping `int(task["row_index"]) -> category` instead of mutating `rows`; after the success block replace the `try: with get_job_lock(...): _write_csv(...)` snippet with `self._apply_categories_under_lock(job_id, merged_path, batch_assignments)`. Delete the final post-loop `_write_csv` block entirely (lines 744–749). Also delete the per-batch `if auto_export:` block (lines 726–740) and instead accumulate `all_successful.extend(successful_batch_indices)` (initialize `all_successful: List[int] = []` before the loop) — Task 4 consumes it; for this task just leave `all_successful` accumulated and unused after the loop.

- [ ] **Step 3.4:** Run `python -m pytest tests/ -q` → PASS.
- [ ] **Step 3.5:** Commit: `fix: apply Ollama categories per-batch under lock so manual edits survive`

---

### Task 4: Auto-export as single end-of-run export + unique temp files

**Files:**
- Modify: `firefly_web/runner.py`
- Test: `tests/test_auto_export.py`

**Interfaces:**
- Consumes: `all_successful` list from Task 3.
- Produces: exactly one `start_firefly_export(job_id=..., options={"auto_from_ollama": True, "row_indices": [...]})` call per categorization run; export temp files named `{stem}_upload_{export_id[:8]}_{batch_no}{suffix}`.

- [ ] **Step 4.1:** Write failing test `tests/test_auto_export.py`:

```python
from pathlib import Path

from firefly_web.runner import JobRunner, _write_csv


FIELDS = ["date", "amount", "description", "category", "external_id"]


def test_auto_export_queued_once_at_end(tmp_settings, tmp_store, monkeypatch, tmp_path):
    merged = tmp_path / "merged.csv"
    rows = [
        {"date": "2025-01-01", "amount": "1.00", "description": f"tx{i}", "category": "", "external_id": f"e{i}"}
        for i in range(1, 6)
    ]
    _write_csv(merged, rows, FIELDS)
    runner = JobRunner(tmp_settings, tmp_store)
    tmp_store.create_job(job_id="job1", input_files=["a.csv"], options={})

    queued = []
    for idx in range(1, 6):
        event_id = tmp_store.create_ollama_event(
            job_id="job1", merge_row_index=idx, external_id=f"e{idx}",
            model="m", categories=["Groceries"], prompt="p",
            tx_date="", tx_amount="", tx_category="", tx_description="",
            tx_source_account="", tx_destination_account="", status="queued",
        )
        queued.append({"row_index": idx, "event_id": event_id})

    monkeypatch.setattr(
        "firefly_web.runner.categorize_ollama_batch_with_trace",
        lambda rows, **kw: {"categories": ["Groceries"] * len(rows), "row_ids": [], "prompt": "p", "response": "r"},
    )
    export_calls = []
    monkeypatch.setattr(
        runner, "start_firefly_export",
        lambda job_id, options=None, export_id="": export_calls.append((job_id, options)) or "exp1",
    )

    runner._run_ollama_categorization(
        job_id="job1", merged_path=merged, queued_tasks=queued,
        categories=["Groceries"], ollama_url="http://x", ollama_model="m",
        prompt_template="", temperature=0.0, timeout_seconds=5.0,
        batch_size=2, auto_export=True,
    )

    assert len(export_calls) == 1  # exactly one export for the whole run (3 batches)
    job_id, options = export_calls[0]
    assert job_id == "job1"
    assert sorted(options["row_indices"]) == [1, 2, 3, 4, 5]
    assert options["auto_from_ollama"] is True
```

(Same `create_ollama_event` signature note as Task 3.)

- [ ] **Step 4.2:** Run `python -m pytest tests/test_auto_export.py -q` → FAIL (zero calls recorded).
- [ ] **Step 4.3:** In `_run_ollama_categorization`, after the batch loop but still inside the `try:` (before the `finally:` that clears the cancel flag), add:

```python
            if auto_export and all_successful and not self._is_ollama_cancelled(job_id):
                try:
                    new_export_id = self.start_firefly_export(
                        job_id=job_id,
                        options={
                            "auto_from_ollama": True,
                            "row_indices": sorted(set(all_successful)),
                        },
                    )
                    log(f"Queued auto-export {new_export_id} for {len(set(all_successful))} categorized row(s).")
                except Exception as exc:
                    log(f"Failed to queue auto-export: {exc}")
```

In `_run_firefly_export`, change the temp filename line to:

```python
                tmp_path = merged_path.with_name(f"{merged_path.stem}_upload_{export_id[:8]}_{batch_no}{merged_path.suffix}")
```

- [ ] **Step 4.4:** Run `python -m pytest tests/ -q` → PASS.
- [ ] **Step 4.5:** Commit: `fix: queue one auto-export per categorization run; unique export temp filenames`

---

### Task 5: Page routes + job summary endpoint

**Files:**
- Modify: `firefly_web/app.py`
- Test: `tests/test_pages.py`

**Interfaces:**
- Produces: GET routes `/`, `/history`, `/jobs/{job_id}`, `/jobs/{job_id}/review`, `/jobs/{job_id}/transactions`, `/jobs/{job_id}/balances`, `/jobs/{job_id}/export`, `/config` rendering templates `merge.html`, `history.html`, `job_status.html`, `review.html`, `transactions.html`, `balances.html`, `export.html`, `config.html`. New endpoint `GET /api/jobs/{job_id}/summary` returning `{"job", "review", "total_rows", "categorized_rows", "latest_export"}` — consumed by `stepper.js` (Task 8) and page modules.
- Note: templates don't exist yet; Task 6 creates them. Tests for page GETs are written here but marked xfail until Task 6; the summary endpoint test must pass now.

- [ ] **Step 5.1:** Write `tests/test_pages.py`:

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_settings, tmp_store):
    import firefly_web.app as app_module
    monkeypatch.setattr(app_module, "settings", tmp_settings)
    monkeypatch.setattr(app_module, "store", tmp_store)
    return TestClient(app_module.app)


def test_job_summary_404(client):
    assert client.get("/api/jobs/nope/summary").status_code == 404


def test_job_summary_shape(client, tmp_store):
    tmp_store.create_job(job_id="j1", input_files=["a.csv"], options={})
    payload = client.get("/api/jobs/j1/summary").json()
    assert set(payload) >= {"job", "review", "total_rows", "categorized_rows", "latest_export"}


PAGES = ["/", "/history", "/config", "/jobs/j1", "/jobs/j1/review",
         "/jobs/j1/transactions", "/jobs/j1/balances", "/jobs/j1/export"]


@pytest.mark.xfail(reason="templates land in Task 6", strict=False)
@pytest.mark.parametrize("path", PAGES)
def test_pages_render(client, path):
    assert client.get(path).status_code == 200
```

Add `httpx` to `requirements-dev.txt` if `TestClient` needs it (`pip show httpx` to check; fastapi's TestClient requires it).

- [ ] **Step 5.2:** Run `python -m pytest tests/test_pages.py -q` → summary tests FAIL (endpoint missing).
- [ ] **Step 5.3:** In `firefly_web/app.py`, replace the existing `index` and `config_page` routes with:

```python
def _render_page(request: Request, template: str, context: Dict[str, object] | None = None) -> HTMLResponse:
    payload = {"default_config_path": str(settings.default_config_path), "data_dir": str(settings.data_dir)}
    if context:
        payload.update(context)
    return templates.TemplateResponse(request, template, payload)


@app.get("/", response_class=HTMLResponse)
async def merge_page(request: Request) -> HTMLResponse:
    return _render_page(request, "merge.html", {"nav_active": "merge"})


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request) -> HTMLResponse:
    return _render_page(request, "history.html", {"nav_active": "jobs"})


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request) -> HTMLResponse:
    return _render_page(request, "config.html", {"nav_active": "config"})


_JOB_PAGES = {
    "": ("job_status.html", "status"),
    "review": ("review.html", "review"),
    "transactions": ("transactions.html", "transactions"),
    "balances": ("balances.html", "balances"),
    "export": ("export.html", "export"),
}


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_status_page(request: Request, job_id: str) -> HTMLResponse:
    template, subnav = _JOB_PAGES[""]
    return _render_page(request, template, {"nav_active": "jobs", "job_id": job_id, "subnav_active": subnav})


@app.get("/jobs/{job_id}/{section}", response_class=HTMLResponse)
async def job_section_page(request: Request, job_id: str, section: str) -> HTMLResponse:
    if section not in _JOB_PAGES or section == "":
        raise HTTPException(status_code=404, detail="Unknown job page.")
    template, subnav = _JOB_PAGES[section]
    return _render_page(request, template, {"nav_active": "jobs", "job_id": job_id, "subnav_active": subnav})
```

CAUTION: `/jobs/{job_id}/{section}` must be declared AFTER all `/api/...` routes are registered? No — path is distinct from `/api/jobs/...`; order doesn't matter. But it must not swallow `/jobs/{id}` static assets; there are none. Keep as written.

Then add the summary endpoint next to the other job endpoints:

```python
@app.get("/api/jobs/{job_id}/summary")
async def get_job_summary(job_id: str) -> Dict[str, object]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    review = _compute_duplicate_review_status(job_id)
    total_rows = 0
    categorized_rows = 0
    try:
        merged_path = _resolve_job_merged_path(job_id)
        rows, _ = read_transactions(merged_path)
        total_rows = len(rows)
        categorized_rows = sum(1 for r in rows if str(r.get("category") or "").strip())
    except HTTPException:
        pass
    exports = store.list_firefly_exports(job_id=job_id, limit=1)
    return {
        "job": job,
        "review": review,
        "total_rows": total_rows,
        "categorized_rows": categorized_rows,
        "latest_export": exports[0] if exports else None,
    }
```

- [ ] **Step 5.4:** Run `python -m pytest tests/test_pages.py -q` → summary tests PASS, page tests xfail.
- [ ] **Step 5.5:** Commit: `feat: MPA page routes and job summary endpoint`

---

### Task 6: Base templates and per-page template shells

**Files:**
- Create: `firefly_web/templates/base.html`, `base_job.html`, `merge.html`, `history.html`, `job_status.html`, `review.html`, `transactions.html`, `balances.html`, `export.html`
- Rewrite: `firefly_web/templates/config.html` (extends base; content preserved)
- Create: `firefly_web/static/js/pages/noop.js` (empty file with `export {};`)

**Interfaces:**
- Consumes: routes/context vars from Task 5 (`nav_active`, `job_id`, `subnav_active`).
- Produces: DOM ids preserved from old `index.html` panels so extracted JS keeps working. Element ids that later tasks rely on: `#queue-badge`, `#queue-badge-link`, `#pipeline-rail`, and every id inside the moved panel markup (unchanged).

- [ ] **Step 6.1:** Create `firefly_web/templates/base.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Firefly Merge{% endblock %}</title>
  <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
  <header class="topbar">
    <nav class="topnav">
      <a class="nav-link {% if nav_active == 'merge' %}active{% endif %}" href="/">New merge</a>
      <a class="nav-link {% if nav_active == 'jobs' %}active{% endif %}" href="/history">Jobs</a>
      <a class="nav-link {% if nav_active == 'config' %}active{% endif %}" href="/config">Configuration</a>
      <a id="queue-badge" class="queue-badge" href="#" hidden>working…</a>
    </nav>
  </header>
  <main class="page">
    {% block content %}{% endblock %}
  </main>
  <script type="module" src="/static/js/badge.js"></script>
  <script type="module" src="/static/js/pages/{% block page_script %}noop{% endblock %}.js"></script>
</body>
</html>
```

- [ ] **Step 6.2:** Create `firefly_web/templates/base_job.html`:

```html
{% extends "base.html" %}
{% block content %}
<section class="job-shell" data-job-id="{{ job_id }}">
  <div id="pipeline-rail" class="pipeline-rail" aria-label="Job pipeline"></div>
  <nav class="job-subnav">
    <a class="{% if subnav_active == 'status' %}active{% endif %}" href="/jobs/{{ job_id }}">Status</a>
    <a class="{% if subnav_active == 'review' %}active{% endif %}" href="/jobs/{{ job_id }}/review">Review</a>
    <a class="{% if subnav_active == 'transactions' %}active{% endif %}" href="/jobs/{{ job_id }}/transactions">Transactions</a>
    <a class="{% if subnav_active == 'balances' %}active{% endif %}" href="/jobs/{{ job_id }}/balances">Balances</a>
    <a class="{% if subnav_active == 'export' %}active{% endif %}" href="/jobs/{{ job_id }}/export">Export</a>
  </nav>
  {% block job_content %}{% endblock %}
</section>
{% endblock %}
```

- [ ] **Step 6.3:** Create `merge.html`. Content = `{% extends "base.html" %}`, title "New merge", `page_script` block → `merge`. Body: move the merge form markup from old `index.html` lines 91–139 (`#merge-form-panel` section) into `{% block content %}`, with these edits: delete the "Import Merged/Categorized CSV" and "Optional Duplicates CSV" file inputs and the "Import As Completed Job" button (import flow is deleted); delete the "Dedupe Scope" label+select (lines 121–124); keep `no_dedup` and `dedupe_first_only` checkboxes and the `push_firefly` checkbox; keep drop-zone and file input ids unchanged. Below the form add the recent-jobs strip:

```html
<section class="panel" id="recent-jobs-panel">
  <h2>Recent jobs</h2>
  <div id="recent-jobs-list" class="recent-jobs"></div>
  <p class="hint" id="recent-jobs-empty" hidden>No jobs yet. Upload bank files above to start your first merge.</p>
</section>
```

- [ ] **Step 6.4:** Create `history.html` (extends base, title "Jobs", `page_script` → `jobs`). Move the history table markup from old `index.html` lines 549–end (`#history-workspace`) into the content block; retitle heading to "Jobs"; keep table/element ids.
- [ ] **Step 6.5:** Create the five job templates, each `{% extends "base_job.html" %}` with `{% block job_content %}`:
  - `job_status.html` (`page_script` → `status`): move `#job-panel` markup (old lines 142–164), minus the empty-state block (`#job-empty-state`) — replace with `<p class="hint" id="job-missing" hidden>This job does not exist. <a href="/history">Back to jobs</a>.</p>`.
  - `review.html` (`page_script` → `review`): move `#duplicates-panel` markup (lines 165–252), minus its empty-state block.
  - `transactions.html` (`page_script` → `transactions`): move `#transactions-panel` markup (lines 253–358), minus empty-state; append the Ollama audit markup from `#ollama-panel` (lines 359–423) wrapped in `<details class="cat-log"><summary>Categorization log</summary> …moved markup… </details>`.
  - `balances.html` (`page_script` → `balances`): move `#analytics-panel` markup (lines 424–439), minus empty-state.
  - `export.html` (`page_script` → `export`): move `#export-panel` markup (lines 440–548), minus empty-state.
  - In all moved markup delete any "Open Latest Job" / "Go To History" buttons and per-panel `empty-state` divs.
- [ ] **Step 6.6:** Rewrite `config.html`: wrap the existing `<main>` content (System Configuration panels, lines 18–end) in `{% extends "base.html" %}` / `{% block content %}`; delete its standalone `<html>/<head>/<body>` and its old topnav (including the "Ollama" nav link); `page_script` → `config`. Change line 31 `firefly_secret` input to `type="password"` and add after both secret and token inputs: `<button type="button" class="reveal-btn" data-reveal="firefly_secret">Show</button>` (and `data-reveal="firefly_token"`).
- [ ] **Step 6.7:** Create `firefly_web/static/js/pages/noop.js` containing `export {};`. Remove the xfail marker from `tests/test_pages.py::test_pages_render`.
- [ ] **Step 6.8:** Run `python -m pytest tests/test_pages.py -q` → all PASS (pages render 200 even though JS modules are missing — script tags 404 harmlessly outside the browser).
- [ ] **Step 6.9:** Commit: `feat: MPA templates with base layout, job shell, and masked secrets`

---

### Task 7: Design tokens, stylesheet rewrite, fonts

**Files:**
- Rewrite: `firefly_web/static/styles.css`
- Create: `firefly_web/static/fonts/` (IBMPlexSans-Regular.woff2, IBMPlexSans-SemiBold.woff2, IBMPlexMono-Regular.woff2)

- [ ] **Step 7.1:** Download fonts (build machine has network):

```bash
mkdir -p firefly_web/static/fonts && cd firefly_web/static/fonts
curl -fLo IBMPlexSans-Regular.woff2 "https://cdn.jsdelivr.net/npm/@ibm/plex@6.4.1/IBM-Plex-Sans/fonts/complete/woff2/IBMPlexSans-Regular.woff2"
curl -fLo IBMPlexSans-SemiBold.woff2 "https://cdn.jsdelivr.net/npm/@ibm/plex@6.4.1/IBM-Plex-Sans/fonts/complete/woff2/IBMPlexSans-SemiBold.woff2"
curl -fLo IBMPlexMono-Regular.woff2 "https://cdn.jsdelivr.net/npm/@ibm/plex@6.4.1/IBM-Plex-Mono/fonts/complete/woff2/IBMPlexMono-Regular.woff2"
file *.woff2   # each must report: Web Open Font Format (Version 2)
```

If any URL 404s, try version `@6.0.0`, then `npm pack @ibm/plex` and extract. If fonts cannot be obtained, STOP and report to the manager — do not substitute another font. The CSS below degrades to system fonts if files are absent, so the task can still proceed with manager approval.

- [ ] **Step 7.2:** Replace `firefly_web/static/styles.css` entirely with the reconciliation-bench stylesheet. Full content:

```css
/* ---- Fonts ------------------------------------------------------------ */
@font-face { font-family: "Plex Sans"; src: url("/static/fonts/IBMPlexSans-Regular.woff2") format("woff2"); font-weight: 400; font-display: swap; }
@font-face { font-family: "Plex Sans"; src: url("/static/fonts/IBMPlexSans-SemiBold.woff2") format("woff2"); font-weight: 600; font-display: swap; }
@font-face { font-family: "Plex Mono"; src: url("/static/fonts/IBMPlexMono-Regular.woff2") format("woff2"); font-weight: 400; font-display: swap; }

/* ---- Tokens ----------------------------------------------------------- */
:root {
  --paper: #FAFAF7;
  --panel: #FFFFFF;
  --ink: #1A2B22;
  --ink-soft: #5A6B62;
  --ledger: #2F6B4F;
  --ledger-soft: #E7F0EB;
  --credit: #2F6B4F;
  --debit: #A8442E;
  --flag: #B7791F;
  --flag-soft: #FBF3E4;
  --rule: #D9D9D2;
  --danger: #8C2F1F;
  --font-ui: "Plex Sans", system-ui, sans-serif;
  --font-num: "Plex Mono", ui-monospace, monospace;
  --radius: 4px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #141815;
    --panel: #1C221E;
    --ink: #E4E9E4;
    --ink-soft: #93A198;
    --ledger: #5CA37F;
    --ledger-soft: #24352C;
    --credit: #5CA37F;
    --debit: #D3765C;
    --flag: #D9A441;
    --flag-soft: #33280F;
    --rule: #333B35;
    --danger: #D06A55;
  }
}

/* ---- Base ------------------------------------------------------------- */
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink); font: 15px/1.5 var(--font-ui); }
h1, h2, h3 { font-weight: 600; line-height: 1.2; margin: 0 0 .5rem; }
h1 { font-size: 1.4rem; } h2 { font-size: 1.1rem; }
a { color: var(--ledger); }
code, .mono { font-family: var(--font-num); font-size: .92em; }
.hint { color: var(--ink-soft); font-size: .88rem; }

/* ---- Top navigation --------------------------------------------------- */
.topbar { border-bottom: 1px solid var(--rule); background: var(--panel); }
.topnav { display: flex; align-items: center; gap: .25rem; max-width: 1200px; margin: 0 auto; padding: .5rem 1rem; }
.nav-link { padding: .4rem .8rem; border-radius: var(--radius); text-decoration: none; color: var(--ink); }
.nav-link.active { background: var(--ledger); color: #fff; }
.nav-link:not(.active):hover { background: var(--ledger-soft); }
.queue-badge { margin-left: auto; font-family: var(--font-num); font-size: .8rem; color: var(--flag); text-decoration: none; padding: .25rem .6rem; border: 1px solid var(--flag); border-radius: 999px; }

/* ---- Page shell ------------------------------------------------------- */
.page { max-width: 1200px; margin: 0 auto; padding: 1rem; }
.panel { background: var(--panel); border: 1px solid var(--rule); border-radius: var(--radius); padding: 1rem; margin-bottom: 1rem; }

/* ---- Pipeline rail (signature) ---------------------------------------- */
.pipeline-rail { display: flex; gap: 0; margin: .75rem 0 1rem; border: 1px solid var(--rule); border-radius: var(--radius); overflow-x: auto; background: var(--panel); }
.rail-step { flex: 1 1 0; min-width: 130px; padding: .55rem .9rem; border-right: 1px solid var(--rule); position: relative; }
.rail-step:last-child { border-right: 0; }
.rail-step .step-name { font-weight: 600; font-size: .85rem; }
.rail-step .step-count { font-family: var(--font-num); font-size: .8rem; color: var(--ink-soft); display: block; }
.rail-step.done .step-name::before { content: "✓ "; color: var(--credit); }
.rail-step.current { box-shadow: inset 0 -3px 0 var(--ledger); }
.rail-step.locked { opacity: .45; }
.rail-step.flagged { background: var(--flag-soft); }

/* ---- Job subnav -------------------------------------------------------- */
.job-subnav { display: flex; gap: .25rem; margin-bottom: 1rem; flex-wrap: wrap; }
.job-subnav a { padding: .3rem .7rem; border: 1px solid var(--rule); border-radius: var(--radius); text-decoration: none; color: var(--ink); font-size: .9rem; }
.job-subnav a.active { background: var(--ledger); border-color: var(--ledger); color: #fff; }

/* ---- Tables ------------------------------------------------------------ */
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: .88rem; }
th { text-align: left; font-weight: 600; border-bottom: 2px solid var(--rule); padding: .4rem .5rem; position: sticky; top: 0; background: var(--panel); }
td { border-bottom: 1px solid var(--rule); padding: .3rem .5rem; vertical-align: top; }
td.num, th.num { text-align: right; font-family: var(--font-num); font-variant-numeric: tabular-nums; white-space: nowrap; }
td.num.credit { color: var(--credit); }
td.num.debit { color: var(--debit); }
tr.dup-suspect { background: var(--flag-soft); }
td .mono { word-break: break-all; }

/* ---- Forms & buttons --------------------------------------------------- */
label { display: block; margin: .6rem 0 .2rem; font-weight: 600; font-size: .88rem; }
input[type="text"], input[type="password"], input[type="number"], select, textarea {
  width: 100%; padding: .45rem .6rem; border: 1px solid var(--rule); border-radius: var(--radius);
  background: var(--panel); color: var(--ink); font: inherit;
}
.inline-option { display: flex; align-items: center; gap: .5rem; font-weight: 400; }
button { font: inherit; padding: .45rem .9rem; border-radius: var(--radius); border: 1px solid var(--ledger); background: var(--ledger); color: #fff; cursor: pointer; }
button:hover { filter: brightness(1.08); }
button.secondary-btn, button.reveal-btn { background: var(--panel); color: var(--ledger); }
button.danger { background: var(--danger); border-color: var(--danger); }
button:disabled { opacity: .5; cursor: not-allowed; }
.drop-zone { border: 2px dashed var(--rule); border-radius: var(--radius); padding: 1.5rem; text-align: center; color: var(--ink-soft); }
.drop-zone.dragover { border-color: var(--ledger); background: var(--ledger-soft); }

/* ---- Misc -------------------------------------------------------------- */
.recent-jobs { display: flex; flex-direction: column; gap: .4rem; }
.recent-job-row { display: flex; gap: 1rem; align-items: baseline; font-size: .9rem; }
.recent-job-row .mono { color: var(--ink-soft); }
.status-chip { font-family: var(--font-num); font-size: .78rem; padding: .1rem .5rem; border-radius: 999px; border: 1px solid var(--rule); }
.status-chip.completed { color: var(--credit); border-color: var(--credit); }
.status-chip.failed { color: var(--danger); border-color: var(--danger); }
.status-chip.running { color: var(--flag); border-color: var(--flag); }
.queue-progress { height: 6px; background: var(--rule); border-radius: 3px; overflow: hidden; }
.queue-progress-fill { height: 100%; width: 0; background: var(--ledger); transition: width .3s; }
details.cat-log > summary, details.advanced-options > summary { cursor: pointer; font-weight: 600; margin: .5rem 0; }
.banner { padding: .6rem .9rem; border-radius: var(--radius); margin-bottom: .8rem; font-size: .9rem; }
.banner.warn { background: var(--flag-soft); border: 1px solid var(--flag); }
.banner.error { background: var(--flag-soft); border: 1px solid var(--danger); color: var(--danger); }
.row-between { display: flex; justify-content: space-between; align-items: center; gap: .5rem; flex-wrap: wrap; }
.small-controls { display: flex; gap: .3rem; flex-wrap: wrap; }
[hidden] { display: none !important; }

@media (max-width: 640px) {
  .page { padding: .5rem; }
  .rail-step { min-width: 105px; padding: .4rem .5rem; }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
}
```

Worker note: old `styles.css` had many class names the moved panel markup still uses (e.g. `subpanel`, `queue-status-card`, pagination buttons). After replacing the stylesheet, grep the new templates for `class="` values and add minimal rules for any that render broken — styling only, never rename classes in markup. Report additions in the task summary.

- [ ] **Step 7.3:** Verify: start dev server (`FIREFLY_WEB_DATA_DIR=/tmp/ff-dev uvicorn firefly_web.app:app --port 8081`), `curl -s localhost:8081/static/styles.css | head -5` shows the font-face block; GET `/` renders.
- [ ] **Step 7.4:** Commit: `feat: reconciliation-bench design tokens, stylesheet, self-hosted IBM Plex`

---

### Task 8: Shared JS modules (api, polling, badge, stepper, tables)

**Files:**
- Create: `firefly_web/static/js/api.js`, `polling.js`, `badge.js`, `stepper.js`, `tables.js`

**Interfaces (produced — page modules in Tasks 9–13 import exactly these):**
- `api.js`: `export async function apiGet(path)`, `export async function apiSend(path, method, body)` (JSON in/out, throws `Error` with server `detail` on non-2xx), `export async function apiUpload(path, formData)`, `export function jobIdFromShell()` (reads `document.querySelector('.job-shell')?.dataset.jobId ?? ""`).
- `polling.js`: `export function startPoll(fn, ms)` → returns `stop()`; runs `fn` immediately then on interval; pauses when `document.hidden`.
- `badge.js`: self-executing; polls `/api/queues/summary` every 5 s; unhides `#queue-badge` when any queue has `queued+running > 0`, sets its text `⚙ {n} running` and href to `/jobs/{job_id}/transactions` (Ollama) or `/jobs/{job_id}/export` (export).
- `stepper.js`: `export function mountStepper(jobId)` → renders into `#pipeline-rail`, polls `/api/jobs/{jobId}/summary` every 4 s; steps: Upload (merged_rows), Review (pending/initial duplicates; state `flagged` if `review.required && !review.confirmed`, `done` if confirmed), Categorize (`categorized_rows/total_rows`), Export (latest_export status). Returns `stop()`.
- `tables.js`: extracted table/pagination/column helpers (see step 8.6).

- [ ] **Step 8.1:** Create `api.js`:

```javascript
export async function apiGet(path) {
  const res = await fetch(path, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(await extractDetail(res));
  return res.json();
}

export async function apiSend(path, method = "POST", body = undefined) {
  const opts = { method, headers: { Accept: "application/json" } };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(await extractDetail(res));
  return res.json();
}

export async function apiUpload(path, formData) {
  const res = await fetch(path, { method: "POST", body: formData });
  if (!res.ok) throw new Error(await extractDetail(res));
  return res.json();
}

async function extractDetail(res) {
  try {
    const data = await res.json();
    return data.detail || `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

export function jobIdFromShell() {
  return document.querySelector(".job-shell")?.dataset.jobId ?? "";
}
```

- [ ] **Step 8.2:** Create `polling.js`:

```javascript
export function startPoll(fn, ms) {
  let timer = null;
  let stopped = false;
  const tick = async () => {
    if (stopped || document.hidden) return;
    try { await fn(); } catch { /* poll errors are non-fatal */ }
  };
  tick();
  timer = setInterval(tick, ms);
  return () => { stopped = true; if (timer) clearInterval(timer); };
}
```

- [ ] **Step 8.3:** Create `badge.js`:

```javascript
import { apiGet } from "./api.js";
import { startPoll } from "./polling.js";

const badge = document.getElementById("queue-badge");
if (badge) {
  startPoll(async () => {
    const data = await apiGet("/api/queues/summary");
    const o = data.ollama?.metrics || {};
    const f = data.firefly_export?.metrics || {};
    const active = (o.queued || 0) + (o.running || 0) + (f.queued || 0) + (f.running || 0);
    if (active > 0) {
      badge.hidden = false;
      badge.textContent = `⚙ ${active} running`;
      if ((o.queued || 0) + (o.running || 0) > 0 && data.ollama.job_id) {
        badge.href = `/jobs/${data.ollama.job_id}/transactions`;
      } else if (data.firefly_export.job_id) {
        badge.href = `/jobs/${data.firefly_export.job_id}/export`;
      }
    } else {
      badge.hidden = true;
    }
  }, 5000);
}
```

- [ ] **Step 8.4:** Create `stepper.js`:

```javascript
import { apiGet } from "./api.js";
import { startPoll } from "./polling.js";

export function mountStepper(jobId) {
  const rail = document.getElementById("pipeline-rail");
  if (!rail || !jobId) return () => {};
  return startPoll(async () => {
    const s = await apiGet(`/api/jobs/${jobId}/summary`);
    const job = s.job || {};
    const review = s.review || {};
    const status = String(job.status || "");
    const merged = job.stats?.merged_rows ?? 0;
    const pendingDup = review.pending_duplicates ?? 0;
    const exportStatus = s.latest_export?.status || "";

    const steps = [
      {
        name: "Upload", count: status === "completed" ? `${merged} merged` : status || "queued",
        cls: status === "completed" ? "done" : status === "failed" ? "flagged" : "current",
      },
      {
        name: "Review",
        count: review.confirmed ? "confirmed" : `${pendingDup} flagged`,
        cls: status !== "completed" ? "locked" : review.confirmed ? "done" : "flagged current",
      },
      {
        name: "Categorize",
        count: `${s.categorized_rows}/${s.total_rows}`,
        cls: status !== "completed" || !review.confirmed ? "locked"
          : s.categorized_rows >= s.total_rows && s.total_rows > 0 ? "done" : "current",
      },
      {
        name: "Export",
        count: exportStatus || "not started",
        cls: status !== "completed" || !review.confirmed ? "locked"
          : exportStatus === "completed" ? "done" : exportStatus ? "current" : "",
      },
    ];
    rail.innerHTML = steps.map(step =>
      `<div class="rail-step ${step.cls}"><span class="step-name">${step.name}</span><span class="step-count">${step.count}</span></div>`
    ).join("");
  }, 4000);
}
```

- [ ] **Step 8.5:** Create `tables.js` by extraction from `static/app.js`. Copy these functions verbatim, add `export` to each, and replace any reference to SPA globals with parameters (each listed function already takes its data as arguments or reads DOM ids that still exist in the new templates): `renderTransactionRow` (app.js:1243), `renderDroppedPairingCell` (1279), `renderCategorySelect` (1307), `updateTxPagination` (1429), `getTxTotalPages` (1425), plus the generic column-management functions (search `app.js` for functions containing `column` in their name — the Excel-style column manager added in commit 247a039; copy the whole group). Where a copied function references a mutable SPA global (e.g. `state.` or `activeJobId`), change the function signature to accept that value as a parameter and update the JSDoc; list every such change in the task summary for manager review.
- [ ] **Step 8.6:** Syntax check: `node --check firefly_web/static/js/*.js` (node is available; if not, `python -c` skip and rely on browser check in next tasks). Commit: `feat: shared ES modules (api, polling, badge, stepper, tables)`

---

### Task 9: Merge page + jobs page modules

**Files:**
- Create: `firefly_web/static/js/pages/merge.js`, `firefly_web/static/js/pages/jobs.js`

**Interfaces:**
- Consumes: `apiGet`, `apiUpload`, `apiSend` from `api.js`.
- Produces: working new-merge submit → redirect to `/jobs/{id}`; jobs list with Open/Delete.

- [ ] **Step 9.1:** Create `pages/merge.js`. Extract from `app.js` the drop-zone + file-hint logic (`updateSelectedFilesHint` app.js:231 and its listeners in the init section — grep `dragover` in app.js) and the merge-form submit handler (grep `merge-form` / `FormData` in app.js). Rewire submit to:

```javascript
import { apiUpload, apiGet } from "../api.js";

async function submitMerge(formData) {
  const data = await apiUpload("/api/jobs", formData);
  window.location.href = `/jobs/${data.job_id}`;
}
```

(The form no longer sends `dedupe_scope` or import-CSV fields.) Then the recent-jobs strip:

```javascript
async function loadRecentJobs() {
  const list = document.getElementById("recent-jobs-list");
  const empty = document.getElementById("recent-jobs-empty");
  const data = await apiGet("/api/jobs?limit=3");
  const jobs = data.jobs || [];
  empty.hidden = jobs.length > 0;
  list.innerHTML = jobs.map(job => `
    <div class="recent-job-row">
      <a href="/jobs/${job.job_id}" class="mono">${job.job_id.slice(0, 12)}</a>
      <span class="status-chip ${job.status}">${job.status}</span>
      <span class="hint">${job.created_at || ""}</span>
      <span class="hint">${job.stats?.merged_rows ?? "-"} merged</span>
    </div>`).join("");
}
loadRecentJobs();
```

Worker: check the real job list item field names in `store.list_jobs` output (`job_id` vs `id`, `created_at`) and match them.

- [ ] **Step 9.2:** Create `pages/jobs.js`: extract the history-table rendering + refresh + delete handlers from `app.js` (grep `history` in app.js; functions `fetchJobs` app.js:719, `deleteJobRequest` app.js:727 move here or into local copies using `api.js`). "Open" action becomes `window.location.href = '/jobs/' + jobId`. Delete keeps its confirm dialog.
- [ ] **Step 9.3:** Manual verify on dev server: upload `test_data/ing_export_jan2025.csv` + `test_data/bunq_export_jan2025.csv` on `/` → browser lands on `/jobs/{id}`; `/history` lists the job; browser console free of errors on both pages.
- [ ] **Step 9.4:** Commit: `feat: merge and jobs pages`

---

### Task 10: Job status page module

**Files:**
- Create: `firefly_web/static/js/pages/status.js`

**Interfaces:**
- Consumes: `apiGet`, `jobIdFromShell`, `mountStepper`, `startPoll`.

- [ ] **Step 10.1:** Create `pages/status.js`: extract job rendering from `app.js` `renderJob` (app.js:611) trimmed of tab-switching calls; poll while status is `queued`/`running`:

```javascript
import { apiGet, jobIdFromShell } from "../api.js";
import { startPoll } from "../polling.js";
import { mountStepper } from "../stepper.js";

const jobId = jobIdFromShell();
mountStepper(jobId);

const stop = startPoll(async () => {
  let job;
  try {
    job = await apiGet(`/api/jobs/${jobId}`);
  } catch {
    document.getElementById("job-missing").hidden = false;
    stop();
    return;
  }
  renderJob(job); // extracted from app.js:611, DOM ids unchanged
  if (job.status === "completed" || job.status === "failed") stop();
}, 3000);
```

(`renderJob` extracted copy: delete all `activateSubTab` / `refreshActiveJobControls` / session-state calls inside it.)
- [ ] **Step 10.2:** Verify on dev server: `/jobs/{id}` of the Task 9 job shows status, logs, artifacts; stepper rail renders 4 steps with live counts; a running job auto-updates to completed. Console clean.
- [ ] **Step 10.3:** Commit: `feat: job status page with pipeline rail`

---

### Task 11: Duplicate review page module

**Files:**
- Create: `firefly_web/static/js/pages/review.js`

**Interfaces:**
- Consumes: `apiGet`, `apiSend`, `jobIdFromShell`, `mountStepper`, `tables.js` pagination helpers.

- [ ] **Step 11.1:** Create `pages/review.js` by extracting from `app.js`: `fetchDuplicateReviewStatus` (826), `buildDuplicateReviewQuery` (835), `fetchDuplicateReviewRows` (846), `restoreDuplicateRowsRequest` (855), `confirmDuplicateReviewRequest` (868), `applyDuplicateReviewGateToActions` (1461), plus the dup-table render/pagination functions adjacent to `getDupTotalPages` (1457) — grep `dup` in app.js for the group. Replace fetch plumbing with `api.js` calls; job id from `jobIdFromShell()`; mount stepper. Confirm button flow unchanged (calls confirm endpoint, re-renders status banner).
- [ ] **Step 11.2:** Verify on dev server with the test-data job (it produces 3 suspected duplicates): review page lists them amber-tinted, restore of one row works (row count moves), Confirm review flips stepper Review step to done. Console clean.
- [ ] **Step 11.3:** Commit: `feat: duplicate review page`

---

### Task 12: Transactions page module (largest)

**Files:**
- Create: `firefly_web/static/js/pages/transactions.js`

**Interfaces:**
- Consumes: everything from `tables.js`, `api.js`, `stepper.js`, `polling.js`.

- [ ] **Step 12.1:** Extract from `app.js` into `pages/transactions.js`: `buildTransactionQuery` (1026), `fetchTransactions` (1041), `loadTransactions` (1201), `clearTransactionState` (1153), `populateSourceFileFilter` (1185), `updateTransactionSummary` (1338), `wireRowCheckboxes` (1352), `wireTransactionDetailButtons` (1369), `buildTransactionRowKey` (1402), `selectTransactionRow` (1408), `openTransactionDetail` (1415), `fetchTransactionDetail` (814), `updateTransactionCategory` (1082), `categorize` (1059), `downloadCategorizedCsv` (1077), plus Ollama queue/audit functions: `fetchOllamaEvents` (736), `fetchOllamaEvent` (769), `stopOllamaQueue` (778), `deleteOllamaQueue` (791), `deleteOllamaQueueItem` (805), `startOllamaPolling` (316)/`stopOllamaPolling` (309) reworked onto `startPoll`. Import row renderers from `tables.js`. Job id from shell; mount stepper. The "categorize with Ollama" and "default categorize" buttons keep their existing ids and handlers.
- [ ] **Step 12.2:** Duplicate-review gate: on load fetch `/api/jobs/{id}/duplicates/review/status`; if `!can_proceed`, disable categorize/export-related buttons and show `<div class="banner warn">Review 88 flagged duplicates before categorizing. <a href="/jobs/{id}/review">Go to review</a></div>` (count from status; insert before the table). This replaces `applyDuplicateReviewGateToActions` behavior on this page.
- [ ] **Step 12.3:** Verify on dev server: transactions table renders with amounts right-aligned mono (`td.num` classes come from `renderTransactionRow` — add `num` + `credit`/`debit` class emission there based on amount sign; this is the one allowed edit inside the extracted renderer). Manual category dropdown saves. Categorization log `<details>` expands and lists events after a default-categorize run. Console clean.
- [ ] **Step 12.4:** Commit: `feat: transactions page with categorization and audit log`

---

### Task 13: Balances + export page modules

**Files:**
- Create: `firefly_web/static/js/pages/balances.js`, `firefly_web/static/js/pages/export.js`

- [ ] **Step 13.1:** `pages/balances.js`: extract `fetchBalances` (1050), `loadBalanceChart` (1329), `loadAnalytics` (1171). Mount stepper.
- [ ] **Step 13.2:** `pages/export.js`: extract `startFireflyExport` (879), `retryFailedFireflyExport` (892), `stopFireflyExport` (905), `deleteFireflyExport` (916), `deleteFireflyExports` (925), `deleteFireflyExportEvents` (936), `fetchFireflyExports` (949), `fetchFireflyExport` (958), `fetchFireflyExportEvents` (967), `fetchFireflyExportEvent` (989), `deleteFireflyExportEvent` (998), and the export table render/pagination group (grep `export` render functions beyond line 1461). Same review-gate banner as Task 12.2. Inline export progress bar uses the existing `queue-progress` markup from the moved panel.
- [ ] **Step 13.3:** Verify on dev server: balances chart renders for the test job; export page shows gate banner until review confirmed, then Start export enabled (do NOT run a real export against Firefly — verify the 400 error surface with unconfigured URL shows as `.banner.error`). Console clean on both pages.
- [ ] **Step 13.4:** Commit: `feat: balances and export pages`

---

### Task 14: Config page module + SPA deletion

**Files:**
- Create: `firefly_web/static/js/pages/config.js` (from existing `static/config.js`)
- Delete: `firefly_web/static/app.js`, `firefly_web/static/config.js`, `firefly_web/templates/index.html`

- [ ] **Step 14.1:** Move `static/config.js` → `static/js/pages/config.js`; wrap as module (add `export {};` at end if needed); add reveal-toggle wiring:

```javascript
document.querySelectorAll(".reveal-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const input = document.getElementById(btn.dataset.reveal);
    const showing = input.type === "text";
    input.type = showing ? "password" : "text";
    btn.textContent = showing ? "Show" : "Hide";
  });
});
```

Remove any `<script>` tag references to old paths in `config.html` (base template loads the module).
- [ ] **Step 14.2:** Delete `static/app.js`, `static/config.js`, `templates/index.html`. Grep for references: `grep -rn "app.js\|index.html\|config.js" firefly_web/ tools/` → fix `tools/` hits in Task 15; `firefly_web/` must have zero hits (except `pages/config.js` itself).
- [ ] **Step 14.3:** Run `python -m pytest tests/ -q` → PASS. Click through all 8 pages on dev server; console clean everywhere.
- [ ] **Step 14.4:** Commit: `feat: config page module; delete SPA (app.js, index.html)`

---

### Task 15: E2E rewrite, race regression in CI, capture_ui update

**Files:**
- Rewrite: `tools/test_e2e.py`
- Modify: `tools/capture_ui.py`
- Create: `.github/workflows/ci.yml`

- [ ] **Step 15.1:** Rewrite `tools/test_e2e.py` as a requests-based flow test that self-hosts the app:

```python
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

        print("E2E OK")
        return 0
    finally:
        server.terminate()
        server.wait(timeout=10)


if __name__ == "__main__":
    sys.exit(main())
```

Worker: check `categorize/default` response key (`updated` vs other name) in `apply_categories` return and fix the assertion to the real key.

- [ ] **Step 15.2:** Run `python tools/test_e2e.py` → "E2E OK", exit 0.
- [ ] **Step 15.3:** Update `tools/capture_ui.py`: replace tab-clicking logic with page navigation. Page list: `[("/", "merge"), ("/history", "jobs"), ("/config", "config")]` plus, when a `--job-id` argument is given, the five job pages. Keep desktop+mobile profiles and screenshot naming (`{profile}_{label}.png`). Also assert zero console errors per page (collect `page.on("console")`, fail on `type == "error"`).
- [ ] **Step 15.4:** Create `.github/workflows/ci.yml`:

```yaml
name: Tests

on:
  push:
  pull_request:

jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: python -m pytest tests/ -q
      - run: python tools/test_e2e.py
```

- [ ] **Step 15.5:** Commit: `test: MPA e2e flow, CI workflow, capture_ui page sweep`

---

### Task 16: Docs, final sweep, user review handoff

**Files:**
- Modify: `README.md`, `WEBAPP.md` (update page/URL descriptions, remove SPA/tab references, remove import-as-completed-job and dedupe-scope docs, document `/jobs/{id}/...` URLs and the pipeline rail)

- [ ] **Step 16.1:** Update docs as above; regenerate screenshots: run merge via e2e-style upload on dev server, then `python tools/capture_ui.py --base-url http://localhost:8081 --job-id <id> --out-dir output_check/ui`; embed/refresh referenced screenshots in README if it references any.
- [ ] **Step 16.2:** Full check: `python -m pytest tests/ -q && python tools/test_e2e.py` → all green.
- [ ] **Step 16.3:** Start the user-review dev server: `FIREFLY_WEB_DATA_DIR=/tmp/ff-review uvicorn firefly_web.app:app --host 0.0.0.0 --port 8081` and report the URL (`http://<nas-ip>:8081`) to the user. **STOP. Do not merge to main. User reviews the UI personally and gives explicit approval.**
- [ ] **Step 16.4 (after user approval only):** merge `mpa-migration` → `main`, push, GH Actions builds GHCR image; user runs `docker compose pull && docker compose up -d`.
- [ ] **Step 16.5:** Commit docs: `docs: MPA pages, URLs, updated screenshots`

---

## Self-Review Notes

- Spec coverage: Q1(B)→Task 0 single branch; Q2(A)→Tasks 5–6 page set with categorization log details; Q3(B)→gate banners Tasks 12/13, stepper states Task 8; Q4→redirect Task 9.1, "Jobs" rename Tasks 6/16, recent-jobs strip Task 9.1; Q5(C)→badge Task 8.3, inline progress Task 13; Q6(A, extract-and-trim, per-page modules)→Tasks 8–14; Q7(A)→Task 4; Q8(B)→Task 3; Q9(A)→Task 2; Q10(cut)→Task 2; Q11(A)→Task 0; Q12→Task 15 (+ race test Task 3, CI 15.4); Q13→dev server 8081, fresh DB, GHCR cutover, user review gate Task 16.3; design direction→Task 7 tokens/fonts, Task 8.4 rail, Task 12.3 signed amounts.
- Known judgment points left to workers are explicitly marked ("Worker note", signature checks) and must be reported back in task summaries for manager review.
- Line numbers for `app.js`/`index.html` refer to the baseline commit from Task 0; workers must re-verify with grep before cutting.
