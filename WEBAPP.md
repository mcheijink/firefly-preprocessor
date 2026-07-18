# Web App Notes

Primary documentation is in `README.md`.

## Architecture

`firefly_web` is a server-rendered multi-page app (FastAPI + Jinja2 templates), not a single-page app. There is no client-side router and no `app.js`/`index.html` shell — each page in the table below is a real HTML route returned by `firefly_web/app.py`, styled with a self-hosted IBM Plex stylesheet (`firefly_web/static/styles.css`) and progressively enhanced by a small per-page ES module under `firefly_web/static/js/pages/`.

| URL | Template | Page module |
|-----|----------|-------------|
| `GET /` | `merge.html` | `js/pages/merge.js` |
| `GET /history` | `history.html` | `js/pages/jobs.js` |
| `GET /config` | `config.html` | `js/pages/config.js` |
| `GET /jobs/{id}` | `job_status.html` | `js/pages/status.js` |
| `GET /jobs/{id}/review` | `review.html` | `js/pages/review.js` |
| `GET /jobs/{id}/transactions` | `transactions.html` | `js/pages/transactions.js` |
| `GET /jobs/{id}/balances` | `balances.html` | `js/pages/balances.js` |
| `GET /jobs/{id}/export` | `export.html` | `js/pages/export.js` |

Job pages share a layout (`base_job.html`) with the pipeline rail and job sub-nav; all pages share `base.html` for the topbar and queue badge. Shared client logic (API fetch helpers, polling, table rendering, the stepper, the queue badge) lives in `firefly_web/static/js/*.js` and is imported by the page modules — there's no monolithic front-end bundle.

## Testing

CI (`.github/workflows/ci.yml`) runs on every push/PR:

```bash
python -m pytest tests/ -q
python tools/test_e2e.py
```

`tools/test_e2e.py` self-hosts uvicorn on a random free port with a temp data dir and drives the real HTTP API (upload -> merge -> review -> confirm -> categorize -> download) with `requests` — no browser involved. Run both locally before pushing; they're fast (a few seconds combined).

## Screenshots

Use `tools/capture_ui.py` for a full visual sweep of every page, at desktop and mobile widths:

```bash
python tools/capture_ui.py --base-url http://localhost:PORT --out-dir output_check/ui
python tools/capture_ui.py --base-url http://localhost:PORT --job-id <completed-job-id> --out-dir output_check/ui
```

Without `--job-id` it captures the three top-level pages (merge/jobs/config). With `--job-id` it also captures the five `/jobs/{id}/...` pages, for 16 PNGs total (8 pages x desktop/mobile). It fails (exit 1) on any real browser console error; benign resource-404s on a fresh job page are tolerated. `output_check/` is gitignored — screenshots there are for local inspection, not committed. The committed reference screenshots in `docs/screenshots/` (used by `README.md`) are regenerated the same way and copied in by hand when the UI changes meaningfully.

If Playwright is not installed:

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium
```
