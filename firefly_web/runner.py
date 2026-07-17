"""Background job runner for merge and dedupe workflows."""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from firefly_merge.main import FIELDNAMES, summarize_firefly_result, upload_to_firefly

from .categorization import build_ollama_prompt, categorize_ollama_batch_with_trace, categorize_ollama_with_trace
from .locks import get_job_lock
from .settings import Settings
from .store import JobStore


class JobRunner:
    def __init__(self, settings: Settings, store: JobStore) -> None:
        self.settings = settings
        self.store = store
        self._control_lock = threading.Lock()
        self._cancelled_ollama_jobs: set[str] = set()
        self._cancelled_firefly_exports: set[str] = set()

    def stop_ollama_queue(self, job_id: str) -> Dict[str, int | str]:
        token = str(job_id or "").strip()
        if not token:
            return {"job_id": "", "queued_cancelled": 0, "running": 0}
        with self._control_lock:
            self._cancelled_ollama_jobs.add(token)
        queued_cancelled = self.store.fail_queued_ollama_events(token, "Cancelled by user.")
        running = self.store.count_running_ollama_events(token)
        if running <= 0:
            self._clear_ollama_cancelled(token)
        return {"job_id": token, "queued_cancelled": queued_cancelled, "running": running}

    def stop_firefly_export(self, export_id: str) -> Dict[str, int | str]:
        token = str(export_id or "").strip()
        if not token:
            return {"export_id": "", "queued_cancelled": 0, "running": 0}
        with self._control_lock:
            self._cancelled_firefly_exports.add(token)
        queued_cancelled = self.store.fail_queued_firefly_export_events(token, "Cancelled by user.")
        running = self.store.count_running_firefly_export_events(export_id=token)
        if running <= 0:
            self._clear_firefly_cancelled(token)
        return {"export_id": token, "queued_cancelled": queued_cancelled, "running": running}

    def _is_ollama_cancelled(self, job_id: str) -> bool:
        token = str(job_id or "").strip()
        if not token:
            return False
        with self._control_lock:
            return token in self._cancelled_ollama_jobs

    def _clear_ollama_cancelled(self, job_id: str) -> None:
        token = str(job_id or "").strip()
        if not token:
            return
        with self._control_lock:
            self._cancelled_ollama_jobs.discard(token)

    def _is_firefly_cancelled(self, export_id: str) -> bool:
        token = str(export_id or "").strip()
        if not token:
            return False
        with self._control_lock:
            return token in self._cancelled_firefly_exports

    def _clear_firefly_cancelled(self, export_id: str) -> None:
        token = str(export_id or "").strip()
        if not token:
            return
        with self._control_lock:
            self._cancelled_firefly_exports.discard(token)

    def start_job(
        self,
        job_id: str,
        input_dir: Path,
        output_dir: Path,
        config_path: Path,
        options: Dict[str, object],
    ) -> None:
        thread = threading.Thread(
            target=self._run_job,
            args=(job_id, input_dir, output_dir, config_path, options),
            daemon=True,
        )
        thread.start()

    def _run_job(
        self,
        job_id: str,
        input_dir: Path,
        output_dir: Path,
        config_path: Path,
        options: Dict[str, object],
    ) -> None:
        self.store.set_running(job_id)

        def log(message: str) -> None:
            self.store.append_log(job_id, message)

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            merged_path = (output_dir / "merged.csv").resolve()
            duplicates_path = (output_dir / "merged_duplicates.csv").resolve()
            reconciliation_path = (output_dir / "merged_reconciliation.csv").resolve()

            cmd = [
                sys.executable,
                "bank_merge_firefly.py",
                "--input-dir",
                str(input_dir),
                "--out",
                str(merged_path),
                "-c",
                str(config_path),
                "--verbose",
            ]

            if bool(options.get("no_dedup")):
                cmd.append("--no-dedup")
            if bool(options.get("dedupe_first_only")):
                cmd.append("--dedupe-first-only")
            if bool(options.get("push_firefly")):
                cmd.append("--push-firefly")
                cmd.extend(self._firefly_overrides_from_env())

            log("Executing merge pipeline.")
            log(f"Command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                cwd=str(self.settings.base_dir),
                capture_output=True,
                text=True,
                check=False,
            )

            if result.stdout.strip():
                for line in result.stdout.splitlines():
                    log(f"[stdout] {line}")
            if result.stderr.strip():
                for line in result.stderr.splitlines():
                    log(f"[stderr] {line}")

            if result.returncode != 0:
                raise RuntimeError(f"Merge command failed with exit code {result.returncode}.")
            if not merged_path.exists():
                raise FileNotFoundError(f"Expected merged output was not created: {merged_path}")

            stats = {
                "merged_rows": _count_csv_rows(merged_path),
                "duplicate_rows": _count_csv_rows(duplicates_path),
                "global_duplicates_added": 0,
                "global_rows_inserted": 0,
            }
            artifacts = {
                "merged_csv": str(merged_path),
                "duplicates_csv": str(duplicates_path) if duplicates_path.exists() else "",
                "reconciliation_csv": str(reconciliation_path) if reconciliation_path.exists() else "",
            }
            self.store.set_completed(
                job_id=job_id,
                artifacts=artifacts,
                stats=stats,
                message="Merge job completed successfully.",
            )
        except Exception as exc:
            log(f"Job failed: {exc}")
            self.store.set_failed(job_id, str(exc))

    def start_firefly_export(
        self,
        job_id: str,
        options: Dict[str, object] | None = None,
        export_id: str = "",
    ) -> str:
        token = str(export_id or "").strip() or uuid.uuid4().hex
        existing = self.store.get_firefly_export(token)
        if existing is None:
            self.store.create_firefly_export(export_id=token, job_id=job_id, options=options or {})
        thread = threading.Thread(
            target=self._run_firefly_export,
            args=(token, job_id, options or {}),
            daemon=True,
        )
        thread.start()
        return token

    def _run_firefly_export(self, export_id: str, job_id: str, options: Dict[str, object]) -> None:
        self.store.set_firefly_export_running(export_id)

        def log(message: str) -> None:
            self.store.append_firefly_export_log(export_id, message)

        try:
            job = self.store.get_job(job_id)
            if job is None:
                raise RuntimeError("Merge job not found.")
            artifacts = job.get("artifacts") or {}
            merged_path_raw = str(artifacts.get("merged_csv") or "").strip()
            if not merged_path_raw:
                raise RuntimeError("Merged CSV is not available for this job.")
            merged_path = Path(merged_path_raw)
            if not merged_path.exists():
                raise RuntimeError(f"Merged CSV does not exist: {merged_path}")

            rows, _ = _read_csv(merged_path)
            if not rows:
                raise RuntimeError("Merged CSV has no rows to export.")

            selected_set: set[int] | None = None
            selected_raw = options.get("row_indices") if isinstance(options, dict) else None
            if isinstance(selected_raw, list):
                parsed: set[int] = set()
                for item in selected_raw:
                    try:
                        value = int(item)
                    except (TypeError, ValueError):
                        continue
                    if value > 0:
                        parsed.add(value)
                selected_set = {idx for idx in parsed if 1 <= idx <= len(rows)}
                if not selected_set:
                    raise RuntimeError("No valid rows selected for export.")

            firefly_cfg = self._resolve_firefly_upload_config()
            export_events: List[Dict[str, Any]] = []
            for idx, row in enumerate(rows, 1):
                if selected_set is not None and idx not in selected_set:
                    continue
                event_id = self.store.create_firefly_export_event(
                    export_id=export_id,
                    job_id=job_id,
                    merge_row_index=idx,
                    external_id=str(row.get("external_id") or ""),
                    tx_date=str(row.get("date") or ""),
                    tx_amount=str(row.get("amount") or ""),
                    tx_category=str(row.get("category") or ""),
                    tx_description=str(row.get("description") or ""),
                    tx_source_account=str(row.get("source_account") or ""),
                    tx_destination_account=str(row.get("destination_account") or ""),
                    status="queued",
                )
                export_events.append({"event_id": event_id, "row_index": idx})

            log(f"Starting Firefly export for job {job_id}.")
            log(f"CSV: {merged_path}")
            log(f"Rows queued: {len(export_events)}")
            retry_source = str((options or {}).get("retry_failed_from_export_id") or "").strip()
            if retry_source:
                log(f"Retry mode from export {retry_source}.")
            if selected_set is not None:
                log(f"Row filter active: {len(selected_set)} row(s) selected.")

            adaptive_cfg = self._resolve_firefly_adaptive_config(firefly_cfg)
            current_batch_size = int(adaptive_cfg["initial_batch_size"])
            target_seconds = float(adaptive_cfg["target_seconds"])
            log(
                "Adaptive batching: "
                f"{'enabled' if adaptive_cfg['enabled'] else 'disabled'}, "
                f"target <= {target_seconds:.2f}s per upload "
                f"(timeout {float(firefly_cfg['timeout']):.2f}s, ratio {float(adaptive_cfg['target_ratio']):.2f}), "
                f"batch range {int(adaptive_cfg['min_batch_size'])}-{int(adaptive_cfg['max_batch_size'])}, "
                f"initial {current_batch_size}."
            )

            exported_rows = 0
            failed_rows = 0
            exported_batches = 0
            failed_batches = 0
            cursor = 0
            batch_no = 0
            summary_lines: List[str] = []
            base_cfg = dict(firefly_cfg)
            base_cfg.pop("batch_size", None)

            while cursor < len(export_events):
                if self._is_firefly_cancelled(export_id):
                    cancelled_count = self.store.fail_queued_firefly_export_events(export_id, "Cancelled by user.")
                    log(f"Export cancelled by user. Remaining queued events marked failed: {cancelled_count}.")
                    raise RuntimeError("Export cancelled by user.")
                remaining = len(export_events) - cursor
                batch_size = min(max(1, int(current_batch_size)), remaining)
                batch_no += 1
                chunk = export_events[cursor : cursor + batch_size]
                chunk_rows = [rows[int(item["row_index"]) - 1] for item in chunk]

                request_payload = json.dumps(
                    {
                        "batch_number": batch_no,
                        "batch_size": batch_size,
                        "target_seconds": round(target_seconds, 4),
                        "timeout_seconds": float(firefly_cfg.get("timeout") or 30.0),
                        "export_id": export_id,
                        "job_id": job_id,
                        "cursor": cursor,
                        "remaining_before": remaining,
                    },
                    ensure_ascii=True,
                )
                for item in chunk:
                    self.store.set_firefly_export_event_running(
                        event_id=int(item["event_id"]),
                        batch_number=batch_no,
                        batch_size=batch_size,
                        request_payload=request_payload,
                    )

                tmp_path = merged_path.with_name(f"{merged_path.stem}_upload_{batch_no}{merged_path.suffix}")
                _write_csv(tmp_path, chunk_rows, FIELDNAMES)
                log(f"[firefly] Batch {batch_no}: {tmp_path.name} ({batch_size} rows)")
                started = time.perf_counter()
                try:
                    result = upload_to_firefly(
                        csv_path=tmp_path,
                        firefly_cfg=base_cfg,
                        config_dir=self.settings.default_config_path.parent,
                        vlog=log,
                    )
                    elapsed = max(0.001, time.perf_counter() - started)
                    summary = summarize_firefly_result(result)
                    response_payload = summary or json.dumps(result or {}, ensure_ascii=True)
                    http_status = _extract_firefly_status_code(result)
                    for item in chunk:
                        self.store.complete_firefly_export_event(
                            event_id=int(item["event_id"]),
                            response_payload=response_payload,
                            error_text="",
                            http_status=http_status,
                            request_payload=request_payload,
                        )
                    exported_rows += len(chunk)
                    exported_batches += 1
                    summary_lines.append(f"Batch {batch_no}: {response_payload}")
                    if summary:
                        log(f"[firefly] Batch {batch_no} response:\n{summary}")

                    if adaptive_cfg["enabled"]:
                        next_size = _estimate_next_batch_size(
                            current_size=batch_size,
                            elapsed_seconds=elapsed,
                            target_seconds=target_seconds,
                            min_size=int(adaptive_cfg["min_batch_size"]),
                            max_size=int(adaptive_cfg["max_batch_size"]),
                        )
                        current_batch_size = min(next_size, max(1, len(export_events) - (cursor + batch_size)))
                        if current_batch_size <= 0:
                            current_batch_size = int(adaptive_cfg["min_batch_size"])
                        log(
                            f"[firefly] Batch {batch_no} took {elapsed:.2f}s, "
                            f"next batch size -> {current_batch_size}"
                        )
                except Exception as exc:
                    failed_batches += 1
                    failed_rows += len(chunk)
                    err_text = str(exc)
                    http_status = _extract_status_from_error_text(err_text)
                    for item in chunk:
                        self.store.complete_firefly_export_event(
                            event_id=int(item["event_id"]),
                            response_payload="",
                            error_text=err_text,
                            http_status=http_status,
                            request_payload=request_payload,
                        )
                    log(f"[firefly] Batch {batch_no} failed: {err_text}")
                    current_batch_size = max(int(adaptive_cfg["min_batch_size"]), batch_size // 2)
                finally:
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass

                cursor += batch_size

            stats = {
                "queued_rows": len(export_events),
                "exported_rows": exported_rows,
                "failed_rows": failed_rows,
                "batches": exported_batches + failed_batches,
                "successful_batches": exported_batches,
                "failed_batches": failed_batches,
                "adaptive_batching": bool(adaptive_cfg["enabled"]),
                "target_seconds": round(target_seconds, 3),
            }
            if summary_lines:
                _summary_sep = "\n\n"
                log(f"Firefly response summary:\n{_summary_sep.join(summary_lines)}")

            if failed_rows == 0:
                self.store.set_firefly_export_completed(
                    export_id=export_id,
                    stats=stats,
                    message="Firefly export completed successfully.",
                )
                return

            self.store.set_firefly_export_failed(
                export_id=export_id,
                error=f"Firefly export finished with partial failures. Exported rows: {exported_rows}, failed rows: {failed_rows}.",
                stats=stats,
                message="Firefly export finished with partial failures.",
            )
        except Exception as exc:
            log(f"Export failed: {exc}")
            pending = self.store.list_firefly_export_events(
                limit=5000,
                offset=0,
                export_id=export_id,
                status_group="queue",
                include_payload=False,
                sort_by="id",
                sort_dir="asc",
            )
            for item in pending:
                self.store.complete_firefly_export_event(
                    event_id=int(item.get("id") or 0),
                    response_payload="",
                    error_text=f"Export aborted: {exc}",
                )
            self.store.set_firefly_export_failed(export_id, str(exc))
        finally:
            self._clear_firefly_cancelled(export_id)

    def _load_file_firefly_config(self) -> Dict[str, Any]:
        path = self.settings.default_config_path
        if not path.exists():
            return {}
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}
        if not isinstance(loaded, dict):
            return {}
        return loaded

    def _resolve_firefly_upload_config(self) -> Dict[str, Any]:
        cfg = self.store.get_system_config()
        firefly_cfg = dict((cfg.get("firefly") or {}) if isinstance(cfg, dict) else {})
        importer_cfg = dict((cfg.get("importer") or {}) if isinstance(cfg, dict) else {})
        firefly_cfg["json_config"] = str(importer_cfg.get("json_path") or firefly_cfg.get("json_config") or "").strip()

        if not firefly_cfg["json_config"]:
            firefly_cfg["json_config"] = str(os.environ.get("FIREFLY_JSON") or "").strip()
        if not firefly_cfg["json_config"]:
            file_cfg = self._load_file_firefly_config()
            file_importer_cfg = file_cfg.get("importer", {}) if isinstance(file_cfg, dict) else {}
            file_firefly_cfg = file_cfg.get("firefly", {}) if isinstance(file_cfg, dict) else {}
            firefly_cfg["json_config"] = str(
                (file_importer_cfg.get("json_path") if isinstance(file_importer_cfg, dict) else "")
                or (file_firefly_cfg.get("json_config") if isinstance(file_firefly_cfg, dict) else "")
                or ""
            ).strip()

        firefly_cfg["url"] = str(firefly_cfg.get("url") or "").strip()
        firefly_cfg["secret"] = str(firefly_cfg.get("secret") or "").strip()
        firefly_cfg["token"] = str(firefly_cfg.get("token") or "").strip()
        if not firefly_cfg["url"]:
            raise RuntimeError("Firefly upload URL is not configured.")
        if not firefly_cfg["json_config"]:
            raise RuntimeError(
                "Firefly importer JSON path is not configured. Set it in Configuration -> Firefly CSV Importer."
            )

        timeout_raw = firefly_cfg.get("timeout", 30)
        batch_raw = firefly_cfg.get("batch_size", 50)
        try:
            firefly_cfg["timeout"] = max(1.0, float(timeout_raw))
        except (TypeError, ValueError):
            firefly_cfg["timeout"] = 30.0
        try:
            firefly_cfg["batch_size"] = max(1, int(batch_raw))
        except (TypeError, ValueError):
            firefly_cfg["batch_size"] = 50
        return firefly_cfg

    def _resolve_firefly_adaptive_config(self, firefly_cfg: Dict[str, Any]) -> Dict[str, Any]:
        cfg = self.store.get_system_config()
        firefly_block = cfg.get("firefly", {}) if isinstance(cfg, dict) else {}
        if not isinstance(firefly_block, dict):
            firefly_block = {}

        timeout_seconds = float(firefly_cfg.get("timeout") or 30.0)
        base_batch_size = max(1, int(firefly_cfg.get("batch_size") or 50))
        enabled = bool(firefly_block.get("adaptive_batch_enabled", True))
        try:
            target_ratio = float(firefly_block.get("adaptive_target_timeout_ratio", 0.75))
        except (TypeError, ValueError):
            target_ratio = 0.75
        target_ratio = min(max(target_ratio, 0.1), 0.95)
        try:
            min_batch_size = max(1, int(firefly_block.get("adaptive_min_batch_size", 1)))
        except (TypeError, ValueError):
            min_batch_size = 1
        try:
            max_batch_size = max(min_batch_size, int(firefly_block.get("adaptive_max_batch_size", base_batch_size)))
        except (TypeError, ValueError):
            max_batch_size = base_batch_size

        initial_batch_size = min(max_batch_size, max(min_batch_size, base_batch_size))
        return {
            "enabled": enabled,
            "target_ratio": target_ratio,
            "target_seconds": timeout_seconds * target_ratio,
            "min_batch_size": min_batch_size,
            "max_batch_size": max_batch_size,
            "initial_batch_size": initial_batch_size,
        }

    def start_ollama_categorization(
        self,
        job_id: str,
        merged_path: Path,
        row_indices: List[int] | None,
        overwrite: bool,
        categories: List[str],
        ollama_url: str,
        ollama_model: str,
        prompt_template: str,
        temperature: float,
        timeout_seconds: float,
        batch_size: int = 1,
        auto_export: bool = False,
    ) -> Dict[str, Any]:
        rows, _ = _read_csv(merged_path)
        selected = set(int(x) for x in row_indices) if row_indices is not None else None
        queue_batch_size = max(1, int(batch_size or 1))
        queued_tasks: List[Dict[str, Any]] = []
        skipped = 0
        for idx, row in enumerate(rows, 1):
            if selected is not None and idx not in selected:
                skipped += 1
                continue
            existing = (row.get("category") or "").strip()
            if existing and not overwrite:
                skipped += 1
                continue
            if queue_batch_size <= 1:
                prompt = build_ollama_prompt(row=row, categories=categories, prompt_template=prompt_template)
            else:
                prompt = "[Batch mode] Prompt will be generated when this batch starts."
            event_id = self.store.create_ollama_event(
                job_id=job_id,
                merge_row_index=idx,
                external_id=str(row.get("external_id") or ""),
                model=ollama_model,
                categories=categories,
                prompt=prompt,
                tx_date=str(row.get("date") or ""),
                tx_amount=str(row.get("amount") or ""),
                tx_category=str(row.get("category") or ""),
                tx_description=str(row.get("description") or ""),
                tx_source_account=str(row.get("source_account") or ""),
                tx_destination_account=str(row.get("destination_account") or ""),
                status="queued",
            )
            queued_tasks.append({"row_index": idx, "event_id": event_id})

        if queued_tasks:
            thread = threading.Thread(
                target=self._run_ollama_categorization,
                args=(
                    job_id,
                    merged_path,
                    queued_tasks,
                    categories,
                    ollama_url,
                    ollama_model,
                    prompt_template,
                    temperature,
                    timeout_seconds,
                    max(1, int(batch_size or 1)),
                    bool(auto_export),
                ),
                daemon=True,
            )
            thread.start()

        return {"queued": len(queued_tasks), "skipped": skipped, "total_rows": len(rows), "export_id": ""}

    def _run_ollama_categorization(
        self,
        job_id: str,
        merged_path: Path,
        queued_tasks: List[Dict[str, Any]],
        categories: List[str],
        ollama_url: str,
        ollama_model: str,
        prompt_template: str,
        temperature: float,
        timeout_seconds: float,
        batch_size: int,
        auto_export: bool = False,
    ) -> None:
        def log(message: str) -> None:
            self.store.append_log(job_id, f"[ollama] {message}")

        try:
            rows, fieldnames = _read_csv(merged_path)
        except Exception as exc:
            for task in queued_tasks:
                event_id = int(task.get("event_id") or 0)
                if event_id:
                    self.store.complete_ollama_event(event_id, response_text="", error_text=f"Failed to read merged CSV: {exc}")
            return

        pipeline_batch_size = max(1, int(batch_size or 1))
        if auto_export:
            log("Auto-export enabled: categorized batches will be queued for export immediately.")

        try:
            for task_batch in _chunk_items(queued_tasks, pipeline_batch_size):
                if self._is_ollama_cancelled(job_id):
                    cancelled = self.store.fail_queued_ollama_events(job_id, "Cancelled by user.")
                    log(f"Ollama queue cancelled by user. Remaining queued events marked failed: {cancelled}.")
                    break

                valid_tasks: List[Dict[str, Any]] = []
                for task in task_batch:
                    event_id = int(task.get("event_id") or 0)
                    idx = int(task.get("row_index") or 0)
                    if not event_id:
                        continue
                    if idx <= 0 or idx > len(rows):
                        self.store.complete_ollama_event(event_id, response_text="", error_text="Row index is out of range.")
                        continue
                    self.store.set_ollama_event_running(event_id)
                    valid_tasks.append({"event_id": event_id, "row_index": idx})

                if not valid_tasks:
                    continue

                batch_rows = [rows[int(task["row_index"]) - 1] for task in valid_tasks]
                response_text = ""
                prompt_text = ""
                assigned_categories: List[str] = []
                successful_batch_indices: List[int] = []

                try:
                    if len(batch_rows) == 1:
                        trace = categorize_ollama_with_trace(
                            row=batch_rows[0],
                            ollama_url=ollama_url,
                            model=ollama_model,
                            categories=categories,
                            prompt_template=prompt_template,
                            temperature=temperature,
                            timeout=timeout_seconds,
                        )
                        assigned_categories = [str(trace.get("category") or "").strip() or "Other"]
                        prompt_text = str(trace.get("prompt") or "")
                        response_text = str(trace.get("response") or "")
                    else:
                        trace = categorize_ollama_batch_with_trace(
                            rows=batch_rows,
                            ollama_url=ollama_url,
                            model=ollama_model,
                            categories=categories,
                            prompt_template=prompt_template,
                            temperature=temperature,
                            timeout=timeout_seconds,
                        )
                        prompt_text = str(trace.get("prompt") or "")
                        response_text = str(trace.get("response") or "")
                        raw_categories = trace.get("categories") or []
                        assigned_categories = [str(item or "").strip() or "Other" for item in raw_categories]
                        if len(assigned_categories) < len(batch_rows):
                            assigned_categories.extend(["Other"] * (len(batch_rows) - len(assigned_categories)))
                        elif len(assigned_categories) > len(batch_rows):
                            assigned_categories = assigned_categories[: len(batch_rows)]

                    for idx, task in enumerate(valid_tasks):
                        row_idx = int(task["row_index"]) - 1
                        category = assigned_categories[idx] if idx < len(assigned_categories) else "Other"
                        rows[row_idx]["category"] = category
                        successful_batch_indices.append(int(task["row_index"]))
                        self.store.complete_ollama_event(
                            int(task["event_id"]),
                            response_text=response_text,
                            error_text="",
                            prompt_text=prompt_text,
                        )
                except Exception as exc:
                    for task in valid_tasks:
                        self.store.complete_ollama_event(
                            int(task["event_id"]),
                            response_text=response_text,
                            error_text=str(exc),
                            prompt_text=prompt_text or None,
                        )
                    continue

                if not successful_batch_indices:
                    continue

                try:
                    with get_job_lock(job_id):
                        _write_csv(merged_path, rows, fieldnames)
                except Exception:
                    # Keep processing queue even if persistence fails once.
                    pass

                if auto_export:
                    try:
                        new_export_id = self.start_firefly_export(
                            job_id=job_id,
                            options={
                                "auto_from_ollama": True,
                                "batch_mode": True,
                                "row_indices": sorted(set(successful_batch_indices)),
                            },
                        )
                        log(
                            f"Queued auto-export {new_export_id} for {len(successful_batch_indices)} categorized row(s)."
                        )
                    except Exception as exc:
                        log(f"Failed to queue auto-export batch: {exc}")
        finally:
            self._clear_ollama_cancelled(job_id)

        try:
            with get_job_lock(job_id):
                _write_csv(merged_path, rows, fieldnames)
        except Exception:
            # Event states already captured. CSV write failures are intentionally silent here.
            pass

    def _firefly_overrides_from_env(self) -> List[str]:
        cfg = self.store.get_system_config()
        firefly_cfg = cfg.get("firefly", {}) if isinstance(cfg, dict) else {}
        importer_cfg = cfg.get("importer", {}) if isinstance(cfg, dict) else {}

        pairs = [
            ("--firefly-url", str(firefly_cfg.get("url") or "")),
            ("--firefly-secret", str(firefly_cfg.get("secret") or "")),
            ("--firefly-token", str(firefly_cfg.get("token") or "")),
            ("--firefly-json", str(importer_cfg.get("json_path") or "")),
            ("--firefly-timeout", str(firefly_cfg.get("timeout") or "")),
            ("--firefly-batch-size", str(firefly_cfg.get("batch_size") or "")),
        ]

        # Environment variables still override persisted config when present.
        env_mapping = {
            "FIREFLY_URL": "--firefly-url",
            "FIREFLY_SECRET": "--firefly-secret",
            "FIREFLY_TOKEN": "--firefly-token",
            "FIREFLY_JSON": "--firefly-json",
            "FIREFLY_TIMEOUT": "--firefly-timeout",
            "FIREFLY_BATCH_SIZE": "--firefly-batch-size",
        }
        by_flag: Dict[str, str] = {flag: value for flag, value in pairs if value}
        for env_name, flag in env_mapping.items():
            env_value = os.environ.get(env_name)
            if env_value:
                by_flag[flag] = env_value

        args: List[str] = []
        for flag in [
            "--firefly-url",
            "--firefly-secret",
            "--firefly-token",
            "--firefly-json",
            "--firefly-timeout",
            "--firefly-batch-size",
        ]:
            value = by_flag.get(flag, "")
            if value:
                args.extend([flag, value])
        return args


def _read_csv(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return rows, fieldnames


def _write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def _count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def _chunk_items(items: List[Dict[str, Any]], size: int) -> List[List[Dict[str, Any]]]:
    safe_size = max(1, int(size or 1))
    return [items[idx : idx + safe_size] for idx in range(0, len(items), safe_size)]


def _estimate_next_batch_size(
    current_size: int,
    elapsed_seconds: float,
    target_seconds: float,
    min_size: int,
    max_size: int,
) -> int:
    safe_current = max(1, int(current_size or 1))
    safe_elapsed = max(0.001, float(elapsed_seconds or 0.001))
    safe_target = max(0.1, float(target_seconds or 0.1))
    per_item = safe_elapsed / safe_current
    if per_item <= 0:
        return safe_current
    ideal = int(safe_target / per_item)
    ideal = max(min_size, min(max_size, max(1, ideal)))
    down = max(min_size, int(round(safe_current * 0.5)))
    up = min(max_size, int(round(safe_current * 1.5)))
    return max(down, min(up, ideal))


def _extract_firefly_status_code(result: Any) -> int:
    if isinstance(result, dict):
        for key in ("status", "status_code", "code", "http_status"):
            value = result.get(key)
            try:
                number = int(value)
            except (TypeError, ValueError):
                continue
            if 100 <= number <= 599:
                return number
    return 200


def _extract_status_from_error_text(text: str) -> int:
    token = str(text or "")
    match = re.search(r"status\s+(\d{3})", token, flags=re.IGNORECASE)
    if not match:
        return 0
    try:
        code = int(match.group(1))
    except (TypeError, ValueError):
        return 0
    if 100 <= code <= 599:
        return code
    return 0
