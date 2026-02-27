"""SQLite persistence for jobs, logs, and global dedupe fingerprints."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class JobStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    options_json TEXT NOT NULL,
                    input_files_json TEXT NOT NULL,
                    artifacts_json TEXT NOT NULL DEFAULT '{}',
                    stats_json TEXT NOT NULL DEFAULT '{}',
                    error TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL DEFAULT '',
                    logs TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS fingerprints (
                    fingerprint TEXT PRIMARY KEY,
                    external_id TEXT NOT NULL DEFAULT '',
                    job_id TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ollama_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    started_at TEXT NOT NULL DEFAULT '',
                    finished_at TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    job_id TEXT NOT NULL DEFAULT '',
                    merge_row_index INTEGER NOT NULL DEFAULT 0,
                    external_id TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    categories_json TEXT NOT NULL DEFAULT '[]',
                    tx_date TEXT NOT NULL DEFAULT '',
                    tx_amount TEXT NOT NULL DEFAULT '',
                    tx_category TEXT NOT NULL DEFAULT '',
                    tx_description TEXT NOT NULL DEFAULT '',
                    tx_source_account TEXT NOT NULL DEFAULT '',
                    tx_destination_account TEXT NOT NULL DEFAULT '',
                    prompt TEXT NOT NULL DEFAULT '',
                    response TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS firefly_exports (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    options_json TEXT NOT NULL DEFAULT '{}',
                    stats_json TEXT NOT NULL DEFAULT '{}',
                    error TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL DEFAULT '',
                    logs TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS firefly_export_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    export_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT NOT NULL DEFAULT '',
                    finished_at TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    batch_number INTEGER NOT NULL DEFAULT 0,
                    batch_size INTEGER NOT NULL DEFAULT 0,
                    merge_row_index INTEGER NOT NULL DEFAULT 0,
                    external_id TEXT NOT NULL DEFAULT '',
                    tx_date TEXT NOT NULL DEFAULT '',
                    tx_amount TEXT NOT NULL DEFAULT '',
                    tx_category TEXT NOT NULL DEFAULT '',
                    tx_description TEXT NOT NULL DEFAULT '',
                    tx_source_account TEXT NOT NULL DEFAULT '',
                    tx_destination_account TEXT NOT NULL DEFAULT '',
                    request_payload TEXT NOT NULL DEFAULT '',
                    response_payload TEXT NOT NULL DEFAULT '',
                    http_status INTEGER NOT NULL DEFAULT 0,
                    error TEXT NOT NULL DEFAULT ''
                );
                """
            )
            _ensure_ollama_event_schema(con)
            _ensure_firefly_export_event_schema(con)
            # Cross-run dedupe is disabled; keep table but clear historical fingerprints.
            con.execute("DELETE FROM fingerprints")
            existing = con.execute("SELECT value_json FROM system_config WHERE key = 'global'").fetchone()
            if existing is None:
                con.execute(
                    "INSERT INTO system_config (key, value_json) VALUES (?, ?)",
                    ("global", json.dumps(default_system_config(), ensure_ascii=True)),
                )
            con.commit()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        # Some mounted filesystems do not support SQLite's default journal locking.
        # MEMORY journal mode keeps the rollback journal in RAM while preserving DB persistence.
        con.execute("PRAGMA journal_mode=MEMORY;")
        con.execute("PRAGMA synchronous=NORMAL;")
        return con

    def create_job(self, job_id: str, input_files: List[str], options: Dict[str, Any]) -> None:
        now = utc_now_iso()
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO jobs (
                    id, status, created_at, updated_at, options_json, input_files_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    "queued",
                    now,
                    now,
                    json.dumps(options, ensure_ascii=True),
                    json.dumps(input_files, ensure_ascii=True),
                ),
            )
            con.commit()

    def append_log(self, job_id: str, message: str) -> None:
        now = utc_now_iso()
        line = f"[{now}] {message}\n"
        with self._connect() as con:
            con.execute(
                """
                UPDATE jobs
                SET logs = logs || ?, updated_at = ?
                WHERE id = ?
                """,
                (line, now, job_id),
            )
            con.commit()

    def set_running(self, job_id: str) -> None:
        now = utc_now_iso()
        with self._connect() as con:
            con.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                ("running", now, job_id),
            )
            con.commit()

    def set_completed(
        self,
        job_id: str,
        artifacts: Dict[str, str],
        stats: Dict[str, Any],
        message: str = "",
    ) -> None:
        now = utc_now_iso()
        with self._connect() as con:
            con.execute(
                """
                UPDATE jobs
                SET status = ?, updated_at = ?, artifacts_json = ?, stats_json = ?, message = ?, error = ''
                WHERE id = ?
                """,
                (
                    "completed",
                    now,
                    json.dumps(artifacts, ensure_ascii=True),
                    json.dumps(stats, ensure_ascii=True),
                    message,
                    job_id,
                ),
            )
            con.commit()

    def set_failed(self, job_id: str, error: str) -> None:
        now = utc_now_iso()
        with self._connect() as con:
            con.execute(
                """
                UPDATE jobs
                SET status = ?, updated_at = ?, error = ?
                WHERE id = ?
                """,
                ("failed", now, error, job_id),
            )
            con.commit()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as con:
            row = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "options": json.loads(row["options_json"] or "{}"),
            "input_files": json.loads(row["input_files_json"] or "[]"),
            "artifacts": json.loads(row["artifacts_json"] or "{}"),
            "stats": json.loads(row["stats_json"] or "{}"),
            "message": row["message"] or "",
            "error": row["error"] or "",
            "logs": row["logs"] or "",
        }

    def list_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        safe_limit = max(1, min(1000, int(limit)))
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT id, status, created_at, updated_at, stats_json, message, error
                FROM jobs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

        out: List[Dict[str, Any]] = []
        for row in rows:
            try:
                stats = json.loads(row["stats_json"] or "{}")
            except json.JSONDecodeError:
                stats = {}
            out.append(
                {
                    "id": row["id"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "stats": stats,
                    "message": row["message"] or "",
                    "error": row["error"] or "",
                }
            )
        return out

    def update_job_options(self, job_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        now = utc_now_iso()
        with self._connect() as con:
            row = con.execute("SELECT options_json FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                return {}
            try:
                current = json.loads(row["options_json"] or "{}")
            except json.JSONDecodeError:
                current = {}
            if not isinstance(current, dict):
                current = {}
            merged = _deep_merge(current, patch or {})
            con.execute(
                "UPDATE jobs SET options_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(merged, ensure_ascii=True), now, job_id),
            )
            con.commit()
            return merged

    def update_job_stats(self, job_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        now = utc_now_iso()
        with self._connect() as con:
            row = con.execute("SELECT stats_json FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                return {}
            try:
                current = json.loads(row["stats_json"] or "{}")
            except json.JSONDecodeError:
                current = {}
            if not isinstance(current, dict):
                current = {}
            merged = dict(current)
            for key, value in (patch or {}).items():
                merged[str(key)] = value
            con.execute(
                "UPDATE jobs SET stats_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(merged, ensure_ascii=True), now, job_id),
            )
            con.commit()
            return merged

    def count_active_firefly_exports(self, job_id: str = "") -> int:
        token = str(job_id or "").strip()
        if token:
            query = "SELECT COUNT(*) AS c FROM firefly_exports WHERE job_id = ? AND status IN ('queued','running')"
            params: Tuple[Any, ...] = (token,)
        else:
            query = "SELECT COUNT(*) AS c FROM firefly_exports WHERE status IN ('queued','running')"
            params = ()
        with self._connect() as con:
            row = con.execute(query, params).fetchone()
        if row is None:
            return 0
        return int(row["c"] or 0)

    def lookup_fingerprint(self, fingerprint: str) -> Optional[str]:
        with self._connect() as con:
            row = con.execute(
                "SELECT external_id FROM fingerprints WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        if row is None:
            return None
        return str(row["external_id"] or "")

    def insert_fingerprint(self, fingerprint: str, external_id: str, job_id: str) -> bool:
        with self._connect() as con:
            try:
                con.execute(
                    """
                    INSERT INTO fingerprints (fingerprint, external_id, job_id, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (fingerprint, external_id or "", job_id, utc_now_iso()),
                )
            except sqlite3.IntegrityError:
                return False
            con.commit()
        return True

    def get_system_config(self) -> Dict[str, Any]:
        with self._connect() as con:
            row = con.execute("SELECT value_json FROM system_config WHERE key = 'global'").fetchone()
        base = default_system_config()
        if row is None:
            return base
        try:
            loaded = json.loads(row["value_json"] or "{}")
        except json.JSONDecodeError:
            loaded = {}
        return _deep_merge(base, loaded)

    def set_system_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        merged = _deep_merge(default_system_config(), payload or {})
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO system_config (key, value_json)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json
                """,
                ("global", json.dumps(merged, ensure_ascii=True)),
            )
            con.commit()
        return merged

    def create_ollama_event(
        self,
        job_id: str,
        merge_row_index: int,
        external_id: str,
        model: str,
        categories: List[str],
        prompt: str,
        tx_date: str = "",
        tx_amount: str = "",
        tx_category: str = "",
        tx_description: str = "",
        tx_source_account: str = "",
        tx_destination_account: str = "",
        status: str = "queued",
    ) -> int:
        state = str(status or "queued").strip().lower()
        if state not in {"queued", "running"}:
            state = "queued"
        started_at = utc_now_iso() if state == "running" else ""
        with self._connect() as con:
            cur = con.execute(
                """
                INSERT INTO ollama_events (
                    created_at, started_at, status, job_id, merge_row_index, external_id, model, categories_json,
                    tx_date, tx_amount, tx_category, tx_description, tx_source_account, tx_destination_account, prompt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    utc_now_iso(),
                    started_at,
                    state,
                    job_id,
                    int(merge_row_index or 0),
                    external_id or "",
                    model or "",
                    json.dumps(categories or [], ensure_ascii=True),
                    tx_date or "",
                    tx_amount or "",
                    tx_category or "",
                    tx_description or "",
                    tx_source_account or "",
                    tx_destination_account or "",
                    prompt or "",
                ),
            )
            con.commit()
            return int(cur.lastrowid or 0)

    def set_ollama_event_running(self, event_id: int) -> None:
        with self._connect() as con:
            con.execute(
                """
                UPDATE ollama_events
                SET started_at = ?, status = ?
                WHERE id = ?
                """,
                (utc_now_iso(), "running", int(event_id)),
            )
            con.commit()

    def complete_ollama_event(
        self,
        event_id: int,
        response_text: str,
        error_text: str = "",
        prompt_text: Optional[str] = None,
    ) -> None:
        status = "failed" if error_text else "completed"
        with self._connect() as con:
            if prompt_text is None:
                con.execute(
                    """
                    UPDATE ollama_events
                    SET finished_at = ?, status = ?, response = ?, error = ?
                    WHERE id = ?
                    """,
                    (utc_now_iso(), status, response_text or "", error_text or "", int(event_id)),
                )
            else:
                con.execute(
                    """
                    UPDATE ollama_events
                    SET finished_at = ?, status = ?, prompt = ?, response = ?, error = ?
                    WHERE id = ?
                    """,
                    (utc_now_iso(), status, prompt_text or "", response_text or "", error_text or "", int(event_id)),
                )
            con.commit()

    def count_ollama_events(self, job_id: str = "", status_group: str = "all") -> int:
        where, params = _build_ollama_where(job_id=job_id, status_group=status_group)
        query = f"SELECT COUNT(*) AS c FROM ollama_events {where}"
        with self._connect() as con:
            row = con.execute(query, params).fetchone()
        if row is None:
            return 0
        return int(row["c"] or 0)

    def list_ollama_events(
        self,
        limit: int = 200,
        offset: int = 0,
        job_id: str = "",
        include_payload: bool = False,
        status_group: str = "all",
        sort_by: str = "id",
        sort_dir: str = "desc",
    ) -> List[Dict[str, Any]]:
        safe_limit = max(1, min(5000, int(limit)))
        safe_offset = max(0, int(offset))
        where, where_params = _build_ollama_where(job_id=job_id, status_group=status_group)
        params = list(where_params)
        order_expr = _ollama_sort_expression(sort_by=sort_by, sort_dir=sort_dir)

        selected_columns = (
            "id, created_at, started_at, finished_at, status, job_id, merge_row_index, "
            "external_id, model, categories_json, tx_date, tx_amount, tx_category, tx_description, "
            "tx_source_account, tx_destination_account, error, prompt, response"
            if include_payload
            else "id, created_at, started_at, finished_at, status, job_id, merge_row_index, "
            "external_id, model, categories_json, tx_date, tx_amount, tx_category, tx_description, "
            "tx_source_account, tx_destination_account, error"
        )
        query = f"""
            SELECT {selected_columns}
            FROM ollama_events
            {where}
            ORDER BY {order_expr}
            LIMIT ? OFFSET ?
        """
        params.append(safe_limit)
        params.append(safe_offset)

        with self._connect() as con:
            rows = con.execute(query, tuple(params)).fetchall()

        out: List[Dict[str, Any]] = []
        for row in rows:
            try:
                categories = json.loads(row["categories_json"] or "[]")
            except json.JSONDecodeError:
                categories = []
            out.append(
                {
                    "id": row["id"],
                    "created_at": row["created_at"],
                    "started_at": row["started_at"],
                    "finished_at": row["finished_at"],
                    "status": row["status"],
                    "job_id": row["job_id"],
                    "merge_row_index": int(row["merge_row_index"] or 0),
                    "external_id": row["external_id"] or "",
                    "model": row["model"] or "",
                    "categories": categories if isinstance(categories, list) else [],
                    "date": row["tx_date"] or "",
                    "amount": row["tx_amount"] or "",
                    "category": row["tx_category"] or "",
                    "description": row["tx_description"] or "",
                    "source_account": row["tx_source_account"] or "",
                    "destination_account": row["tx_destination_account"] or "",
                    "error": row["error"] or "",
                    "prompt": (row["prompt"] or "") if include_payload else "",
                    "response": (row["response"] or "") if include_payload else "",
                }
            )
        return out

    def get_ollama_event(self, event_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as con:
            row = con.execute(
                """
                SELECT id, created_at, started_at, finished_at, status, job_id, merge_row_index,
                       external_id, model, categories_json, tx_date, tx_amount, tx_category, tx_description,
                       tx_source_account, tx_destination_account, prompt, response, error
                FROM ollama_events
                WHERE id = ?
                """,
                (int(event_id),),
            ).fetchone()
        if row is None:
            return None
        try:
            categories = json.loads(row["categories_json"] or "[]")
        except json.JSONDecodeError:
            categories = []
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "status": row["status"],
            "job_id": row["job_id"],
            "merge_row_index": int(row["merge_row_index"] or 0),
            "external_id": row["external_id"] or "",
            "model": row["model"] or "",
            "categories": categories if isinstance(categories, list) else [],
            "date": row["tx_date"] or "",
            "amount": row["tx_amount"] or "",
            "category": row["tx_category"] or "",
            "description": row["tx_description"] or "",
            "source_account": row["tx_source_account"] or "",
            "destination_account": row["tx_destination_account"] or "",
            "prompt": row["prompt"] or "",
            "response": row["response"] or "",
            "error": row["error"] or "",
        }

    def count_active_ollama_events(self, job_id: str = "") -> int:
        token = (job_id or "").strip()
        if token:
            query = "SELECT COUNT(*) AS c FROM ollama_events WHERE job_id = ? AND status IN ('queued','running')"
            params = (token,)
        else:
            query = "SELECT COUNT(*) AS c FROM ollama_events WHERE status IN ('queued','running')"
            params = ()
        with self._connect() as con:
            row = con.execute(query, params).fetchone()
        if row is None:
            return 0
        return int(row["c"] or 0)

    def count_running_ollama_events(self, job_id: str = "") -> int:
        token = (job_id or "").strip()
        if token:
            query = "SELECT COUNT(*) AS c FROM ollama_events WHERE job_id = ? AND status = 'running'"
            params = (token,)
        else:
            query = "SELECT COUNT(*) AS c FROM ollama_events WHERE status = 'running'"
            params = ()
        with self._connect() as con:
            row = con.execute(query, params).fetchone()
        if row is None:
            return 0
        return int(row["c"] or 0)

    def fail_queued_ollama_events(self, job_id: str, error_text: str) -> int:
        token = (job_id or "").strip()
        if not token:
            return 0
        now = utc_now_iso()
        with self._connect() as con:
            cur = con.execute(
                """
                UPDATE ollama_events
                SET finished_at = ?, status = 'failed', error = ?
                WHERE job_id = ? AND status = 'queued'
                """,
                (now, error_text or "Cancelled by user.", token),
            )
            con.commit()
            return int(cur.rowcount or 0)

    def delete_ollama_event(self, event_id: int) -> bool:
        with self._connect() as con:
            cur = con.execute("DELETE FROM ollama_events WHERE id = ?", (int(event_id),))
            con.commit()
            return int(cur.rowcount or 0) > 0

    def delete_ollama_events(self, job_id: str = "", status_group: str = "all") -> int:
        where, params = _build_ollama_where(job_id=job_id, status_group=status_group)
        query = f"DELETE FROM ollama_events {where}"
        with self._connect() as con:
            cur = con.execute(query, params)
            con.commit()
            return int(cur.rowcount or 0)

    def get_ollama_queue_metrics(self, job_id: str = "") -> Dict[str, Any]:
        token = (job_id or "").strip()
        where = "WHERE job_id = ?" if token else ""
        params: Tuple[Any, ...] = (token,) if token else ()
        query = f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END) AS queued,
                SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) AS running,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                MIN(CASE WHEN started_at <> '' THEN started_at END) AS first_started_at,
                MAX(finished_at) AS last_finished_at
            FROM ollama_events
            {where}
        """
        with self._connect() as con:
            row = con.execute(query, params).fetchone()
        if row is None:
            return {
                "total": 0,
                "queued": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
                "first_started_at": "",
                "last_finished_at": "",
            }
        return {
            "total": int(row["total"] or 0),
            "queued": int(row["queued"] or 0),
            "running": int(row["running"] or 0),
            "completed": int(row["completed"] or 0),
            "failed": int(row["failed"] or 0),
            "first_started_at": str(row["first_started_at"] or ""),
            "last_finished_at": str(row["last_finished_at"] or ""),
        }

    def get_latest_active_ollama_job_id(self) -> str:
        with self._connect() as con:
            row = con.execute(
                """
                SELECT job_id
                FROM ollama_events
                WHERE status IN ('queued', 'running') AND job_id <> ''
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return ""
        return str(row["job_id"] or "").strip()

    def create_firefly_export(self, export_id: str, job_id: str, options: Dict[str, Any]) -> None:
        now = utc_now_iso()
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO firefly_exports (
                    id, job_id, status, created_at, updated_at, options_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    export_id,
                    job_id,
                    "queued",
                    now,
                    now,
                    json.dumps(options or {}, ensure_ascii=True),
                ),
            )
            con.commit()

    def get_latest_active_firefly_export(self) -> Optional[Dict[str, Any]]:
        with self._connect() as con:
            row = con.execute(
                """
                SELECT id, job_id, status, created_at, updated_at
                FROM firefly_exports
                WHERE status IN ('queued', 'running')
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"] or "",
            "job_id": row["job_id"] or "",
            "status": row["status"] or "",
            "created_at": row["created_at"] or "",
            "updated_at": row["updated_at"] or "",
        }

    def create_firefly_export_event(
        self,
        export_id: str,
        job_id: str,
        merge_row_index: int,
        external_id: str = "",
        tx_date: str = "",
        tx_amount: str = "",
        tx_category: str = "",
        tx_description: str = "",
        tx_source_account: str = "",
        tx_destination_account: str = "",
        status: str = "queued",
    ) -> int:
        state = str(status or "queued").strip().lower()
        if state not in {"queued", "running"}:
            state = "queued"
        started_at = utc_now_iso() if state == "running" else ""
        with self._connect() as con:
            cur = con.execute(
                """
                INSERT INTO firefly_export_events (
                    export_id, job_id, created_at, started_at, status,
                    merge_row_index, external_id, tx_date, tx_amount, tx_category,
                    tx_description, tx_source_account, tx_destination_account
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    export_id,
                    job_id,
                    utc_now_iso(),
                    started_at,
                    state,
                    int(merge_row_index or 0),
                    external_id or "",
                    tx_date or "",
                    tx_amount or "",
                    tx_category or "",
                    tx_description or "",
                    tx_source_account or "",
                    tx_destination_account or "",
                ),
            )
            con.commit()
            return int(cur.lastrowid or 0)

    def set_firefly_export_event_running(
        self,
        event_id: int,
        batch_number: int,
        batch_size: int,
        request_payload: str = "",
    ) -> None:
        with self._connect() as con:
            con.execute(
                """
                UPDATE firefly_export_events
                SET started_at = ?, status = ?, batch_number = ?, batch_size = ?, request_payload = ?
                WHERE id = ?
                """,
                (
                    utc_now_iso(),
                    "running",
                    int(batch_number or 0),
                    int(batch_size or 0),
                    request_payload or "",
                    int(event_id),
                ),
            )
            con.commit()

    def complete_firefly_export_event(
        self,
        event_id: int,
        response_payload: str = "",
        error_text: str = "",
        http_status: int = 0,
        request_payload: Optional[str] = None,
    ) -> None:
        status = "failed" if error_text else "completed"
        with self._connect() as con:
            if request_payload is None:
                con.execute(
                    """
                    UPDATE firefly_export_events
                    SET finished_at = ?, status = ?, response_payload = ?, http_status = ?, error = ?
                    WHERE id = ?
                    """,
                    (
                        utc_now_iso(),
                        status,
                        response_payload or "",
                        int(http_status or 0),
                        error_text or "",
                        int(event_id),
                    ),
                )
            else:
                con.execute(
                    """
                    UPDATE firefly_export_events
                    SET finished_at = ?, status = ?, request_payload = ?, response_payload = ?, http_status = ?, error = ?
                    WHERE id = ?
                    """,
                    (
                        utc_now_iso(),
                        status,
                        request_payload or "",
                        response_payload or "",
                        int(http_status or 0),
                        error_text or "",
                        int(event_id),
                    ),
                )
            con.commit()

    def count_firefly_export_events(
        self,
        job_id: str = "",
        export_id: str = "",
        status_group: str = "all",
    ) -> int:
        where, params = _build_firefly_export_event_where(
            job_id=job_id,
            export_id=export_id,
            status_group=status_group,
        )
        query = f"SELECT COUNT(*) AS c FROM firefly_export_events {where}"
        with self._connect() as con:
            row = con.execute(query, params).fetchone()
        if row is None:
            return 0
        return int(row["c"] or 0)

    def list_firefly_export_events(
        self,
        limit: int = 200,
        offset: int = 0,
        job_id: str = "",
        export_id: str = "",
        include_payload: bool = False,
        status_group: str = "all",
        sort_by: str = "id",
        sort_dir: str = "asc",
    ) -> List[Dict[str, Any]]:
        safe_limit = max(1, min(5000, int(limit)))
        safe_offset = max(0, int(offset))
        where, where_params = _build_firefly_export_event_where(
            job_id=job_id,
            export_id=export_id,
            status_group=status_group,
        )
        params = list(where_params)
        order_expr = _firefly_export_event_sort_expression(sort_by=sort_by, sort_dir=sort_dir)
        selected_columns = (
            "id, export_id, job_id, created_at, started_at, finished_at, status, "
            "batch_number, batch_size, merge_row_index, external_id, tx_date, tx_amount, tx_category, "
            "tx_description, tx_source_account, tx_destination_account, http_status, error, "
            "request_payload, response_payload"
            if include_payload
            else "id, export_id, job_id, created_at, started_at, finished_at, status, "
            "batch_number, batch_size, merge_row_index, external_id, tx_date, tx_amount, tx_category, "
            "tx_description, tx_source_account, tx_destination_account, http_status, error"
        )
        query = f"""
            SELECT {selected_columns}
            FROM firefly_export_events
            {where}
            ORDER BY {order_expr}
            LIMIT ? OFFSET ?
        """
        params.append(safe_limit)
        params.append(safe_offset)
        with self._connect() as con:
            rows = con.execute(query, tuple(params)).fetchall()

        out: List[Dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "id": int(row["id"] or 0),
                    "export_id": row["export_id"] or "",
                    "job_id": row["job_id"] or "",
                    "created_at": row["created_at"] or "",
                    "started_at": row["started_at"] or "",
                    "finished_at": row["finished_at"] or "",
                    "status": row["status"] or "",
                    "batch_number": int(row["batch_number"] or 0),
                    "batch_size": int(row["batch_size"] or 0),
                    "merge_row_index": int(row["merge_row_index"] or 0),
                    "external_id": row["external_id"] or "",
                    "date": row["tx_date"] or "",
                    "amount": row["tx_amount"] or "",
                    "category": row["tx_category"] or "",
                    "description": row["tx_description"] or "",
                    "source_account": row["tx_source_account"] or "",
                    "destination_account": row["tx_destination_account"] or "",
                    "http_status": int(row["http_status"] or 0),
                    "error": row["error"] or "",
                    "request_payload": (row["request_payload"] or "") if include_payload else "",
                    "response_payload": (row["response_payload"] or "") if include_payload else "",
                }
            )
        return out

    def get_firefly_export_event(self, event_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as con:
            row = con.execute(
                """
                SELECT
                    id, export_id, job_id, created_at, started_at, finished_at, status,
                    batch_number, batch_size, merge_row_index, external_id, tx_date, tx_amount, tx_category,
                    tx_description, tx_source_account, tx_destination_account, request_payload, response_payload,
                    http_status, error
                FROM firefly_export_events
                WHERE id = ?
                """,
                (int(event_id),),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": int(row["id"] or 0),
            "export_id": row["export_id"] or "",
            "job_id": row["job_id"] or "",
            "created_at": row["created_at"] or "",
            "started_at": row["started_at"] or "",
            "finished_at": row["finished_at"] or "",
            "status": row["status"] or "",
            "batch_number": int(row["batch_number"] or 0),
            "batch_size": int(row["batch_size"] or 0),
            "merge_row_index": int(row["merge_row_index"] or 0),
            "external_id": row["external_id"] or "",
            "date": row["tx_date"] or "",
            "amount": row["tx_amount"] or "",
            "category": row["tx_category"] or "",
            "description": row["tx_description"] or "",
            "source_account": row["tx_source_account"] or "",
            "destination_account": row["tx_destination_account"] or "",
            "request_payload": row["request_payload"] or "",
            "response_payload": row["response_payload"] or "",
            "http_status": int(row["http_status"] or 0),
            "error": row["error"] or "",
        }

    def count_active_firefly_export_events(self, job_id: str = "", export_id: str = "") -> int:
        where, params = _build_firefly_export_event_where(
            job_id=job_id,
            export_id=export_id,
            status_group="queue",
        )
        query = f"SELECT COUNT(*) AS c FROM firefly_export_events {where}"
        with self._connect() as con:
            row = con.execute(query, params).fetchone()
        if row is None:
            return 0
        return int(row["c"] or 0)

    def count_running_firefly_export_events(self, job_id: str = "", export_id: str = "") -> int:
        clauses: List[str] = ["status = 'running'"]
        params: List[Any] = []
        token_job = (job_id or "").strip()
        token_export = (export_id or "").strip()
        if token_job:
            clauses.append("job_id = ?")
            params.append(token_job)
        if token_export:
            clauses.append("export_id = ?")
            params.append(token_export)
        where = f"WHERE {' AND '.join(clauses)}"
        query = f"SELECT COUNT(*) AS c FROM firefly_export_events {where}"
        with self._connect() as con:
            row = con.execute(query, tuple(params)).fetchone()
        if row is None:
            return 0
        return int(row["c"] or 0)

    def fail_queued_firefly_export_events(self, export_id: str, error_text: str) -> int:
        token = (export_id or "").strip()
        if not token:
            return 0
        now = utc_now_iso()
        with self._connect() as con:
            cur = con.execute(
                """
                UPDATE firefly_export_events
                SET finished_at = ?, status = 'failed', error = ?
                WHERE export_id = ? AND status = 'queued'
                """,
                (now, error_text or "Cancelled by user.", token),
            )
            con.commit()
            return int(cur.rowcount or 0)

    def delete_firefly_export_event(self, event_id: int) -> bool:
        with self._connect() as con:
            cur = con.execute("DELETE FROM firefly_export_events WHERE id = ?", (int(event_id),))
            con.commit()
            return int(cur.rowcount or 0) > 0

    def delete_firefly_export_events(self, export_id: str, status_group: str = "all") -> int:
        where, params = _build_firefly_export_event_where(
            job_id="",
            export_id=export_id,
            status_group=status_group,
        )
        query = f"DELETE FROM firefly_export_events {where}"
        with self._connect() as con:
            cur = con.execute(query, params)
            con.commit()
            return int(cur.rowcount or 0)

    def get_firefly_export_queue_metrics(self, job_id: str = "", export_id: str = "") -> Dict[str, Any]:
        where, params = _build_firefly_export_event_where(
            job_id=job_id,
            export_id=export_id,
            status_group="all",
        )
        query = f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END) AS queued,
                SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) AS running,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                MIN(CASE WHEN started_at <> '' THEN started_at END) AS first_started_at,
                MAX(finished_at) AS last_finished_at
            FROM firefly_export_events
            {where}
        """
        with self._connect() as con:
            row = con.execute(query, params).fetchone()
        if row is None:
            return {
                "total": 0,
                "queued": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
                "first_started_at": "",
                "last_finished_at": "",
            }
        return {
            "total": int(row["total"] or 0),
            "queued": int(row["queued"] or 0),
            "running": int(row["running"] or 0),
            "completed": int(row["completed"] or 0),
            "failed": int(row["failed"] or 0),
            "first_started_at": str(row["first_started_at"] or ""),
            "last_finished_at": str(row["last_finished_at"] or ""),
        }

    def list_failed_firefly_export_row_indices(self, export_id: str) -> List[int]:
        token = (export_id or "").strip()
        if not token:
            return []
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT DISTINCT merge_row_index
                FROM firefly_export_events
                WHERE export_id = ? AND status = 'failed' AND merge_row_index > 0
                ORDER BY merge_row_index ASC
                """,
                (token,),
            ).fetchall()
        out: List[int] = []
        for row in rows:
            try:
                value = int(row["merge_row_index"] or 0)
            except (TypeError, ValueError):
                value = 0
            if value > 0:
                out.append(value)
        return out

    def append_firefly_export_log(self, export_id: str, message: str) -> None:
        now = utc_now_iso()
        line = f"[{now}] {message}\n"
        with self._connect() as con:
            con.execute(
                """
                UPDATE firefly_exports
                SET logs = logs || ?, updated_at = ?
                WHERE id = ?
                """,
                (line, now, export_id),
            )
            con.commit()

    def set_firefly_export_running(self, export_id: str) -> None:
        now = utc_now_iso()
        with self._connect() as con:
            con.execute(
                "UPDATE firefly_exports SET status = ?, updated_at = ?, error = '' WHERE id = ?",
                ("running", now, export_id),
            )
            con.commit()

    def set_firefly_export_completed(
        self,
        export_id: str,
        stats: Dict[str, Any],
        message: str = "",
    ) -> None:
        now = utc_now_iso()
        with self._connect() as con:
            con.execute(
                """
                UPDATE firefly_exports
                SET status = ?, updated_at = ?, stats_json = ?, message = ?, error = ''
                WHERE id = ?
                """,
                (
                    "completed",
                    now,
                    json.dumps(stats or {}, ensure_ascii=True),
                    message or "",
                    export_id,
                ),
            )
            con.commit()

    def set_firefly_export_failed(
        self,
        export_id: str,
        error: str,
        stats: Optional[Dict[str, Any]] = None,
        message: str = "",
    ) -> None:
        now = utc_now_iso()
        with self._connect() as con:
            if stats is None:
                con.execute(
                    """
                    UPDATE firefly_exports
                    SET status = ?, updated_at = ?, error = ?
                    WHERE id = ?
                    """,
                    ("failed", now, error or "", export_id),
                )
            else:
                con.execute(
                    """
                    UPDATE firefly_exports
                    SET status = ?, updated_at = ?, error = ?, message = ?, stats_json = ?
                    WHERE id = ?
                    """,
                    (
                        "failed",
                        now,
                        error or "",
                        message or "",
                        json.dumps(stats or {}, ensure_ascii=True),
                        export_id,
                    ),
                )
            con.commit()

    def get_firefly_export(self, export_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as con:
            row = con.execute("SELECT * FROM firefly_exports WHERE id = ?", (export_id,)).fetchone()
        if row is None:
            return None
        try:
            options = json.loads(row["options_json"] or "{}")
        except json.JSONDecodeError:
            options = {}
        try:
            stats = json.loads(row["stats_json"] or "{}")
        except json.JSONDecodeError:
            stats = {}
        return {
            "id": row["id"],
            "job_id": row["job_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "options": options,
            "stats": stats,
            "message": row["message"] or "",
            "error": row["error"] or "",
            "logs": row["logs"] or "",
        }

    def list_firefly_exports(self, job_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        safe_limit = max(1, min(500, int(limit)))
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT id, job_id, status, created_at, updated_at, stats_json, message, error
                FROM firefly_exports
                WHERE job_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (job_id, safe_limit),
            ).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            try:
                stats = json.loads(row["stats_json"] or "{}")
            except json.JSONDecodeError:
                stats = {}
            out.append(
                {
                    "id": row["id"],
                    "job_id": row["job_id"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "stats": stats,
                    "message": row["message"] or "",
                    "error": row["error"] or "",
                }
            )
        return out

    def delete_firefly_export(self, export_id: str) -> bool:
        token = (export_id or "").strip()
        if not token:
            return False
        with self._connect() as con:
            row = con.execute("SELECT id FROM firefly_exports WHERE id = ?", (token,)).fetchone()
            if row is None:
                return False
            con.execute("DELETE FROM firefly_export_events WHERE export_id = ?", (token,))
            con.execute("DELETE FROM firefly_exports WHERE id = ?", (token,))
            con.commit()
        return True

    def delete_firefly_exports(self, job_id: str, status_group: str = "all") -> Dict[str, int]:
        token = (job_id or "").strip()
        if not token:
            return {"exports": 0, "events": 0}

        clauses: List[str] = ["job_id = ?"]
        params: List[Any] = [token]
        status_token = (status_group or "all").strip().lower()
        if status_token in {"queue", "queued", "active"}:
            clauses.append("status IN ('queued', 'running')")
        elif status_token in {"completed", "done", "history"}:
            clauses.append("status IN ('completed', 'failed')")

        where = f"WHERE {' AND '.join(clauses)}"
        with self._connect() as con:
            rows = con.execute(f"SELECT id FROM firefly_exports {where}", tuple(params)).fetchall()
            export_ids = [str(row["id"] or "").strip() for row in rows if str(row["id"] or "").strip()]
            if not export_ids:
                return {"exports": 0, "events": 0}

            placeholders = ",".join(["?"] * len(export_ids))
            events_cur = con.execute(
                f"DELETE FROM firefly_export_events WHERE export_id IN ({placeholders})",
                tuple(export_ids),
            )
            exports_cur = con.execute(
                f"DELETE FROM firefly_exports WHERE id IN ({placeholders})",
                tuple(export_ids),
            )
            con.commit()
            return {
                "exports": int(exports_cur.rowcount or 0),
                "events": int(events_cur.rowcount or 0),
            }

    def delete_job(self, job_id: str) -> bool:
        token = (job_id or "").strip()
        if not token:
            return False
        with self._connect() as con:
            row = con.execute("SELECT id FROM jobs WHERE id = ?", (token,)).fetchone()
            if row is None:
                return False
            con.execute("DELETE FROM fingerprints WHERE job_id = ?", (token,))
            con.execute("DELETE FROM firefly_exports WHERE job_id = ?", (token,))
            con.execute("DELETE FROM firefly_export_events WHERE job_id = ?", (token,))
            con.execute("DELETE FROM ollama_events WHERE job_id = ?", (token,))
            con.execute("DELETE FROM jobs WHERE id = ?", (token,))
            con.commit()
        return True


def default_system_config() -> Dict[str, Any]:
    return {
        "firefly": {
            "url": "",
            "secret": "",
            "token": "",
            "json_config": "",
            "timeout": 30,
            "batch_size": 50,
            "adaptive_batch_enabled": True,
            "adaptive_target_timeout_ratio": 0.75,
            "adaptive_min_batch_size": 1,
            "adaptive_max_batch_size": 200,
        },
        "importer": {
            "json_path": "",
        },
        "ollama": {
            "enabled": False,
            "url": "http://localhost:11434",
            "model": "llama3.1:8b",
            "temperature": 0.0,
            "batch_size": 20,
            "auto_export_after_categorize": False,
            "prompt_template": (
                "You categorize financial transactions.\\n"
                "Choose exactly one category from this list:\\n"
                "{categories_csv}\\n"
                "Return only compact JSON with this schema: {\\\"category\\\":\\\"<one category from list>\\\"}\\n"
                "Transaction:\\n"
                "{transaction_json}\\n"
            ),
            "default_categories": [
                "Groceries",
                "Dining",
                "Transport",
                "Utilities",
                "Rent",
                "Insurance",
                "Salary",
                "Transfers (internal)",
                "Health",
                "Subscriptions",
                "Shopping",
                "Travel",
                "Taxes",
                "Entertainment",
                "Other",
            ],
        },
        "merge": {
            "own_accounts": [],
            "account_aliases": {},
            "savings_accounts": {},
        },
    }


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _ensure_ollama_event_schema(con: sqlite3.Connection) -> None:
    columns = {
        "tx_date": "TEXT NOT NULL DEFAULT ''",
        "tx_amount": "TEXT NOT NULL DEFAULT ''",
        "tx_category": "TEXT NOT NULL DEFAULT ''",
        "tx_description": "TEXT NOT NULL DEFAULT ''",
        "tx_source_account": "TEXT NOT NULL DEFAULT ''",
        "tx_destination_account": "TEXT NOT NULL DEFAULT ''",
    }
    existing = {str(row[1]) for row in con.execute("PRAGMA table_info(ollama_events)").fetchall()}
    for name, definition in columns.items():
        if name in existing:
            continue
        con.execute(f"ALTER TABLE ollama_events ADD COLUMN {name} {definition}")

    con.execute("CREATE INDEX IF NOT EXISTS idx_ollama_events_job_status_id ON ollama_events(job_id, status, id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_ollama_events_status_id ON ollama_events(status, id)")


def _ensure_firefly_export_event_schema(con: sqlite3.Connection) -> None:
    columns = {
        "batch_number": "INTEGER NOT NULL DEFAULT 0",
        "batch_size": "INTEGER NOT NULL DEFAULT 0",
        "merge_row_index": "INTEGER NOT NULL DEFAULT 0",
        "external_id": "TEXT NOT NULL DEFAULT ''",
        "tx_date": "TEXT NOT NULL DEFAULT ''",
        "tx_amount": "TEXT NOT NULL DEFAULT ''",
        "tx_category": "TEXT NOT NULL DEFAULT ''",
        "tx_description": "TEXT NOT NULL DEFAULT ''",
        "tx_source_account": "TEXT NOT NULL DEFAULT ''",
        "tx_destination_account": "TEXT NOT NULL DEFAULT ''",
        "request_payload": "TEXT NOT NULL DEFAULT ''",
        "response_payload": "TEXT NOT NULL DEFAULT ''",
        "http_status": "INTEGER NOT NULL DEFAULT 0",
        "error": "TEXT NOT NULL DEFAULT ''",
    }
    existing = {str(row[1]) for row in con.execute("PRAGMA table_info(firefly_export_events)").fetchall()}
    for name, definition in columns.items():
        if name in existing:
            continue
        con.execute(f"ALTER TABLE firefly_export_events ADD COLUMN {name} {definition}")

    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_firefly_export_events_job_export_status_id "
        "ON firefly_export_events(job_id, export_id, status, id)"
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_firefly_export_events_status_id ON firefly_export_events(status, id)")


def _build_ollama_where(job_id: str, status_group: str) -> Tuple[str, Tuple[Any, ...]]:
    clauses: List[str] = []
    params: List[Any] = []
    token = (job_id or "").strip()
    if token:
        clauses.append("job_id = ?")
        params.append(token)

    status_token = (status_group or "all").strip().lower()
    if status_token in {"queue", "queued", "active"}:
        clauses.append("status IN ('queued', 'running')")
    elif status_token in {"completed", "done", "history"}:
        clauses.append("status IN ('completed', 'failed')")

    if not clauses:
        return "", tuple(params)
    return f"WHERE {' AND '.join(clauses)}", tuple(params)


def _build_firefly_export_event_where(job_id: str, export_id: str, status_group: str) -> Tuple[str, Tuple[Any, ...]]:
    clauses: List[str] = []
    params: List[Any] = []
    job_token = (job_id or "").strip()
    export_token = (export_id or "").strip()
    if job_token:
        clauses.append("job_id = ?")
        params.append(job_token)
    if export_token:
        clauses.append("export_id = ?")
        params.append(export_token)

    status_token = (status_group or "all").strip().lower()
    if status_token in {"queue", "queued", "active"}:
        clauses.append("status IN ('queued', 'running')")
    elif status_token in {"completed", "done", "history"}:
        clauses.append("status IN ('completed', 'failed')")

    if not clauses:
        return "", tuple(params)
    return f"WHERE {' AND '.join(clauses)}", tuple(params)


def _ollama_sort_expression(sort_by: str, sort_dir: str) -> str:
    token = (sort_by or "id").strip().lower()
    direction = "DESC" if (sort_dir or "desc").strip().lower() == "desc" else "ASC"
    columns = {
        "id": "id",
        "status": "status",
        "job": "job_id",
        "job_id": "job_id",
        "row": "merge_row_index",
        "merge_row_index": "merge_row_index",
        "model": "model",
        "created": "created_at",
        "created_at": "created_at",
        "finished": "finished_at",
        "finished_at": "finished_at",
        "external_id": "external_id",
        "date": "tx_date",
        "amount": "CAST(REPLACE(tx_amount, ',', '.') AS REAL)",
        "category": "tx_category",
        "description": "tx_description",
        "source_account": "tx_source_account",
        "destination_account": "tx_destination_account",
    }
    expr = columns.get(token, "id")
    return f"{expr} {direction}, id DESC"


def _firefly_export_event_sort_expression(sort_by: str, sort_dir: str) -> str:
    token = (sort_by or "id").strip().lower()
    direction = "DESC" if (sort_dir or "desc").strip().lower() == "desc" else "ASC"
    columns = {
        "id": "id",
        "status": "status",
        "job": "job_id",
        "job_id": "job_id",
        "export": "export_id",
        "export_id": "export_id",
        "row": "merge_row_index",
        "merge_row_index": "merge_row_index",
        "batch": "batch_number",
        "batch_number": "batch_number",
        "date": "tx_date",
        "amount": "CAST(REPLACE(tx_amount, ',', '.') AS REAL)",
        "category": "tx_category",
        "description": "tx_description",
        "source_account": "tx_source_account",
        "destination_account": "tx_destination_account",
        "created": "created_at",
        "created_at": "created_at",
        "finished": "finished_at",
        "finished_at": "finished_at",
        "http_status": "http_status",
    }
    expr = columns.get(token, "id")
    return f"{expr} {direction}, id DESC"
