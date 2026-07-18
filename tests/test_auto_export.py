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
    monkeypatch.setattr(
        "firefly_web.runner.categorize_ollama_with_trace",
        lambda row, **kw: {"category": "Groceries", "prompt": "p", "response": "r"},
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
