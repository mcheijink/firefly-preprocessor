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

    def fake_single(row, **kwargs):
        # batch_size=2 over 3 queued tasks leaves a trailing 1-item chunk,
        # which routes through the single-row code path.
        return {"category": "Groceries", "prompt": "p", "response": "r"}

    monkeypatch.setattr("firefly_web.runner.categorize_ollama_batch_with_trace", fake_batch)
    monkeypatch.setattr("firefly_web.runner.categorize_ollama_with_trace", fake_single)

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
