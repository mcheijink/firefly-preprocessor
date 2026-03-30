"""FastAPI app for the Firefly merge web tool."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import csv
import shutil
import threading
import uuid
import yaml
from contextlib import asynccontextmanager
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response as StarletteResponse

from firefly_merge.main import DUPLICATE_FIELDNAMES, FIELDNAMES

from .categorization import categorize_default
from .locks import get_job_lock
from .runner import JobRunner
from .settings import Settings, load_settings
from .store import JobStore, utc_now_iso
from .transactions import (
    apply_categories,
    build_balance_series,
    get_transaction_review_detail,
    list_duplicate_suspects,
    list_transaction_review,
    read_transactions,
    restore_duplicate_rows,
    set_category_by_row_index,
)


def _safe_filename(name: str) -> str:
    return Path(name or "upload.csv").name.replace("\\", "_").replace("/", "_")


def _ensure_inside(path: Path, root: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid artifact path.") from exc


def _ensure_inside_allowed_dirs(path: Path) -> None:
    """Verify path is within data_dir or config_dir (two valid roots)."""
    resolved = path.resolve()
    for root in (settings.data_dir, settings.config_dir):
        try:
            resolved.relative_to(root.resolve())
            return
        except ValueError:
            pass
    raise HTTPException(status_code=400, detail="Path is outside the allowed directories.")


settings: Settings = load_settings()
store = JobStore(settings.db_path)
runner = JobRunner(settings, store)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class _BasicAuthMiddleware(BaseHTTPMiddleware):
    """Optional HTTP Basic Auth gate (activated when APP_SECRET is set)."""

    def __init__(self, app, secret: str) -> None:
        super().__init__(app)
        self._secret_bytes = secret.encode("utf-8")

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/api/health":
            return await call_next(request)
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth[6:]).decode("utf-8")
                _, _, password = decoded.partition(":")
                if hmac.compare_digest(password.encode("utf-8"), self._secret_bytes):
                    return await call_next(request)
            except Exception:
                pass
        return StarletteResponse(
            content="Unauthorized",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Firefly Merge"'},
            media_type="text/plain",
        )


class _CsrfMiddleware(BaseHTTPMiddleware):
    """Reject cross-origin state-changing requests via Origin header check."""

    _SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    async def dispatch(self, request: Request, call_next):
        if request.method not in self._SAFE_METHODS:
            origin = request.headers.get("Origin", "")
            if origin:
                host = request.headers.get("Host", "")
                origin_host = urlparse(origin).netloc
                if origin_host and origin_host != host:
                    return JSONResponse({"detail": "CSRF check failed."}, status_code=403)
        return await call_next(request)


class _MaxUploadSizeMiddleware(BaseHTTPMiddleware):
    """Reject requests whose declared Content-Length exceeds the configured limit."""

    def __init__(self, app, max_bytes: int) -> None:
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("Content-Length")
        if content_length:
            try:
                if int(content_length) > self._max_bytes:
                    limit_mb = self._max_bytes // (1024 * 1024)
                    return JSONResponse(
                        {"detail": f"Upload size exceeds the {limit_mb} MB limit."},
                        status_code=413,
                    )
            except ValueError:
                pass
        return await call_next(request)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _lifespan(app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    store.initialize()
    yield


app = FastAPI(title="Firefly Merge Web Tool", version="1.0.0", lifespan=_lifespan)

# Middleware is applied in LIFO order — auth added last = outermost (first to run).
if settings.max_upload_bytes > 0:
    app.add_middleware(_MaxUploadSizeMiddleware, max_bytes=settings.max_upload_bytes)
app.add_middleware(_CsrfMiddleware)
if settings.app_secret:
    app.add_middleware(_BasicAuthMiddleware, secret=settings.app_secret)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


class CategorizeRequest(BaseModel):
    row_indices: Optional[List[int]] = None
    overwrite: bool = False
    categories: Optional[List[str]] = None
    timeout_seconds: float = Field(default=60.0, ge=5.0, le=300.0)
    batch_size: Optional[int] = Field(default=None, ge=1, le=200)
    auto_export: Optional[bool] = None


class SystemConfigPayload(BaseModel):
    firefly: Dict[str, object] = Field(default_factory=dict)
    importer: Dict[str, object] = Field(default_factory=dict)
    merge: Dict[str, object] = Field(default_factory=dict)
    ollama: Dict[str, object] = Field(default_factory=dict)


class ManualCategoryUpdateRequest(BaseModel):
    merge_row_index: int = Field(ge=1, le=10_000_000)
    category: str = ""


class FireflyExportRequest(BaseModel):
    force: bool = False


class OllamaQueueStopRequest(BaseModel):
    job_id: str = ""


class DuplicateReviewRestoreRequest(BaseModel):
    duplicate_row_indices: List[int] = Field(default_factory=list)


class ConfigWriteFileRequest(BaseModel):
    path: str = "config/system_config.yml"
    format: str = "yaml"


class ConfigResetRequest(BaseModel):
    clear_uploaded_importer_files: bool = True


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "default_config_path": str(settings.default_config_path),
            "data_dir": str(settings.data_dir),
        },
    )


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "config.html",
        {
            "request": request,
            "default_config_path": str(settings.default_config_path),
            "data_dir": str(settings.data_dir),
        },
    )


@app.get("/api/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/jobs")
async def create_job(
    files: List[UploadFile] = File(...),
    config_file: Optional[UploadFile] = File(default=None),
    dedupe_scope: str = Form(default="within_job"),
    no_dedup: bool = Form(default=False),
    dedupe_first_only: bool = Form(default=False),
    push_firefly: bool = Form(default=False),
) -> Dict[str, str]:
    if not files:
        raise HTTPException(status_code=400, detail="At least one bank statement file is required.")

    dedupe_scope = dedupe_scope.strip().lower()
    if dedupe_scope == "global":
        dedupe_scope = "within_job"
    if dedupe_scope not in {"within_job"}:
        raise HTTPException(status_code=400, detail="dedupe_scope must be within_job.")

    job_id = uuid.uuid4().hex
    job_dir = (settings.jobs_dir / job_id).resolve()
    input_dir = (job_dir / "input").resolve()
    output_dir = (job_dir / "output").resolve()
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_files: List[str] = []
    for uploaded in files:
        filename = _safe_filename(uploaded.filename or "input.csv")
        destination = input_dir / filename
        with destination.open("wb") as handle:
            shutil.copyfileobj(uploaded.file, handle)
        input_files.append(filename)
        await uploaded.close()

    config_path: Path
    if config_file is not None and config_file.filename:
        config_filename = _safe_filename(config_file.filename)
        config_path = (job_dir / config_filename).resolve()
        with config_path.open("wb") as handle:
            shutil.copyfileobj(config_file.file, handle)
        await config_file.close()
    else:
        config_path = settings.default_config_path
        if not config_path.exists():
            raise HTTPException(
                status_code=400,
                detail="No config file was uploaded and no default config is present on the server.",
            )

    config_path = _build_effective_job_config(base_config_path=config_path, job_dir=job_dir)

    options = {
        "dedupe_scope": dedupe_scope,
        "no_dedup": no_dedup,
        "dedupe_first_only": dedupe_first_only,
        "push_firefly": push_firefly,
        "duplicate_review": {
            "required": False,
            "confirmed": False,
            "confirmed_at": "",
            "restored_rows_total": 0,
            "updated_at": utc_now_iso(),
        },
    }
    store.create_job(job_id=job_id, input_files=input_files, options=options)
    store.append_log(job_id, f"Saved {len(input_files)} file(s) for processing.")
    store.append_log(job_id, f"Using config: {config_path}")

    runner.start_job(
        job_id=job_id,
        input_dir=input_dir,
        output_dir=output_dir,
        config_path=config_path,
        options=options,
    )
    return {"job_id": job_id, "status": "queued"}


@app.post("/api/jobs/import")
async def import_merged_job(
    merged_file: UploadFile = File(...),
    duplicates_file: Optional[UploadFile] = File(default=None),
) -> Dict[str, str]:
    raw_name = str(merged_file.filename or "").strip()
    if not raw_name:
        raw_name = "merged_import.csv"

    job_id = uuid.uuid4().hex
    job_dir = (settings.jobs_dir / job_id).resolve()
    input_dir = (job_dir / "input").resolve()
    output_dir = (job_dir / "output").resolve()
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    merged_name = _safe_filename(raw_name)
    merged_input_path = (input_dir / merged_name).resolve()
    with merged_input_path.open("wb") as handle:
        shutil.copyfileobj(merged_file.file, handle)
    await merged_file.close()

    merged_rows, merged_fieldnames = read_transactions(merged_input_path)
    normalized_rows, normalized_fields = _normalize_imported_merged_rows(merged_rows, merged_fieldnames)
    merged_output_path = (output_dir / "merged.csv").resolve()
    _write_rows_csv(merged_output_path, normalized_rows, normalized_fields)

    duplicates_output_path = (output_dir / "merged_duplicates.csv").resolve()
    duplicate_rows_count = 0
    input_files = [merged_name]
    if duplicates_file is not None and duplicates_file.filename:
        dup_name = _safe_filename(duplicates_file.filename)
        dup_input_path = (input_dir / dup_name).resolve()
        with dup_input_path.open("wb") as handle:
            shutil.copyfileobj(duplicates_file.file, handle)
        await duplicates_file.close()
        dup_rows, dup_fields = read_transactions(dup_input_path)
        normalized_dup_rows, normalized_dup_fields = _normalize_imported_duplicates_rows(dup_rows, dup_fields)
        _write_rows_csv(duplicates_output_path, normalized_dup_rows, normalized_dup_fields)
        duplicate_rows_count = len(normalized_dup_rows)
        input_files.append(dup_name)
    elif duplicates_output_path.exists():
        try:
            duplicates_output_path.unlink()
        except OSError:
            pass

    options = {
        "import_mode": "merged_csv",
        "duplicate_review": {
            "required": bool(duplicate_rows_count > 0),
            "confirmed": bool(duplicate_rows_count <= 0),
            "confirmed_at": utc_now_iso() if duplicate_rows_count <= 0 else "",
            "restored_rows_total": 0,
            "updated_at": utc_now_iso(),
        },
    }
    store.create_job(job_id=job_id, input_files=input_files, options=options)
    store.append_log(job_id, f"Imported merged CSV: {merged_name}")
    if duplicate_rows_count:
        store.append_log(job_id, f"Imported duplicates CSV rows: {duplicate_rows_count}")
    store.set_completed(
        job_id=job_id,
        artifacts={
            "merged_csv": str(merged_output_path),
            "duplicates_csv": str(duplicates_output_path) if duplicate_rows_count else "",
            "reconciliation_csv": "",
        },
        stats={
            "merged_rows": len(normalized_rows),
            "duplicate_rows": duplicate_rows_count,
            "global_duplicates_added": 0,
            "global_rows_inserted": 0,
        },
        message="Imported merged CSV as completed job.",
    )
    return {"job_id": job_id, "status": "completed"}


@app.get("/api/jobs")
async def list_jobs(limit: int = 100) -> Dict[str, object]:
    return {"jobs": store.list_jobs(limit=limit)}


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str) -> Dict[str, object]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if str(job.get("status") or "").strip() == "running":
        raise HTTPException(status_code=409, detail="Cannot delete a running job. Stop the job first.")
    deleted = store.delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found.")
    job_dir = (settings.jobs_dir / job_id).resolve()
    if job_dir.exists():
        try:
            _ensure_inside(job_dir, settings.jobs_dir)
            shutil.rmtree(job_dir, ignore_errors=True)
        except HTTPException:
            pass
    return {"status": "deleted", "job_id": job_id}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> Dict[str, object]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    artifact_urls: Dict[str, str] = {}
    for artifact_key, raw_path in (job.get("artifacts") or {}).items():
        if not raw_path:
            continue
        path = Path(raw_path)
        if path.exists():
            artifact_urls[artifact_key] = f"/api/jobs/{job_id}/artifacts/{artifact_key}"
    job["artifact_urls"] = artifact_urls
    return job


@app.get("/api/jobs/{job_id}/transactions")
async def get_job_transactions(
    job_id: str,
    offset: int = 0,
    limit: int = 200,
    include_duplicates: bool = True,
    decision: str = "all",
    search: str = "",
    source_file: str = "",
    sort_by: str = "date",
    sort_dir: str = "asc",
    include_dropped: bool = True,
    include_details: bool = False,
) -> Dict[str, object]:
    merged_path, duplicates_path = _resolve_job_transaction_files(job_id)
    payload = list_transaction_review(
        merged_path=merged_path,
        duplicates_path=duplicates_path if include_dropped else None,
        offset=offset,
        limit=limit,
        include_duplicates=include_duplicates,
        decision=decision,
        search=search,
        source_file=source_file,
        sort_by=sort_by,
        sort_dir=sort_dir,
        summary_only=not bool(include_details),
    )
    cfg = store.get_system_config()
    ollama_cfg = cfg.get("ollama", {}) if isinstance(cfg, dict) else {}
    payload["categories"] = [str(item).strip() for item in list(ollama_cfg.get("default_categories") or []) if str(item).strip()]
    return payload


@app.get("/api/jobs/{job_id}/transactions/detail")
async def get_job_transaction_detail(
    job_id: str,
    row_source: str,
    row_local_index: int,
) -> Dict[str, object]:
    merged_path, duplicates_path = _resolve_job_transaction_files(job_id)
    detail = get_transaction_review_detail(
        merged_path=merged_path,
        duplicates_path=duplicates_path,
        row_source=row_source,
        row_local_index=row_local_index,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Transaction detail not found.")
    return detail


@app.get("/api/jobs/{job_id}/duplicates/review/status")
async def get_duplicate_review_status(job_id: str) -> Dict[str, object]:
    return _compute_duplicate_review_status(job_id)


@app.get("/api/jobs/{job_id}/duplicates/review")
async def list_duplicate_review_rows(
    job_id: str,
    offset: int = 0,
    limit: int = 50,
    search: str = "",
    source_file: str = "",
    sort_by: str = "date",
    sort_dir: str = "asc",
) -> Dict[str, object]:
    merged_path, duplicates_path = _resolve_job_transaction_files(job_id)
    payload = list_duplicate_suspects(
        merged_path=merged_path,
        duplicates_path=duplicates_path,
        offset=offset,
        limit=limit,
        search=search,
        source_file=source_file,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    payload["review"] = _compute_duplicate_review_status(job_id)
    return payload


@app.post("/api/jobs/{job_id}/duplicates/review/restore")
async def restore_duplicate_review_rows(
    job_id: str,
    payload: DuplicateReviewRestoreRequest = Body(...),
) -> Dict[str, object]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if str(job.get("status") or "").strip() != "completed":
        raise HTTPException(status_code=400, detail="Duplicate review is available only for completed jobs.")
    if store.count_active_ollama_events(job_id=job_id) > 0:
        raise HTTPException(status_code=409, detail="Stop Ollama queue before changing duplicate decisions.")
    if store.count_active_firefly_exports(job_id=job_id) > 0:
        raise HTTPException(status_code=409, detail="Stop Firefly export queue before changing duplicate decisions.")

    merged_path, duplicates_path = _resolve_job_transaction_files(job_id)
    if duplicates_path is None or not duplicates_path.exists():
        raise HTTPException(status_code=400, detail="No duplicates file available for this job.")

    selected = sorted(set(int(x) for x in (payload.duplicate_row_indices or []) if int(x) > 0))
    if not selected:
        raise HTTPException(status_code=400, detail="Select at least one duplicate row to restore.")

    with get_job_lock(job_id):
        result = restore_duplicate_rows(
            merged_path=merged_path,
            duplicates_path=duplicates_path,
            duplicate_row_indices=selected,
        )
    store.update_job_stats(
        job_id=job_id,
        patch={
            "merged_rows": int(result.get("merged_rows") or 0),
            "duplicate_rows": int(result.get("remaining_duplicates") or 0),
        },
    )

    current_job = store.get_job(job_id) or {}
    options = current_job.get("options") if isinstance(current_job.get("options"), dict) else {}
    review = options.get("duplicate_review") if isinstance(options.get("duplicate_review"), dict) else {}
    restored_total = int(review.get("restored_rows_total") or 0) + int(result.get("restored_rows") or 0)
    remaining = int(result.get("remaining_duplicates") or 0)
    store.update_job_options(
        job_id=job_id,
        patch={
            "duplicate_review": {
                "required": bool(remaining > 0),
                "confirmed": bool(remaining <= 0),
                "confirmed_at": utc_now_iso() if remaining <= 0 else "",
                "restored_rows_total": restored_total,
                "updated_at": utc_now_iso(),
            }
        },
    )
    store.append_log(
        job_id,
        f"Duplicate review override: restored {int(result.get('restored_rows') or 0)} row(s); remaining duplicates: {remaining}.",
    )
    return {"status": "ok", **result, "review": _compute_duplicate_review_status(job_id)}


@app.post("/api/jobs/{job_id}/duplicates/review/confirm")
async def confirm_duplicate_review(job_id: str) -> Dict[str, object]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if str(job.get("status") or "").strip() != "completed":
        raise HTTPException(status_code=400, detail="Duplicate review is available only for completed jobs.")
    status = _compute_duplicate_review_status(job_id)
    pending = int(status.get("pending_duplicates") or 0)
    store.update_job_options(
        job_id=job_id,
        patch={
            "duplicate_review": {
                "required": bool(pending > 0),
                "confirmed": True,
                "confirmed_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
            }
        },
    )
    store.append_log(job_id, f"Duplicate review confirmed. Pending duplicate rows at confirm time: {pending}.")
    return {"status": "confirmed", "review": _compute_duplicate_review_status(job_id)}


@app.get("/api/jobs/{job_id}/transactions/categorized.csv")
async def download_categorized_transactions(job_id: str, include_uncategorized: bool = False) -> Response:
    merged_path = _resolve_job_merged_path(job_id)
    rows, fieldnames = read_transactions(merged_path)
    if include_uncategorized:
        selected = rows
    else:
        selected = [row for row in rows if str(row.get("category") or "").strip()]

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames or [])
    if fieldnames:
        writer.writeheader()
        for row in selected:
            writer.writerow({name: row.get(name, "") for name in fieldnames})
    content = output.getvalue()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="categorized_{job_id}.csv"'},
    )


@app.get("/api/jobs/{job_id}/balances")
async def get_job_balances(job_id: str) -> Dict[str, object]:
    merged_path = _resolve_job_merged_path(job_id)
    return build_balance_series(merged_path)


@app.post("/api/jobs/{job_id}/categorize/default")
async def categorize_default_endpoint(job_id: str, payload: CategorizeRequest = Body(...)) -> Dict[str, object]:
    _ensure_duplicate_review_ready(job_id)
    merged_path = _resolve_job_merged_path(job_id)
    with get_job_lock(job_id):
        result = apply_categories(
            path=merged_path,
            row_indices=payload.row_indices,
            assign_category=categorize_default,
            overwrite=payload.overwrite,
        )
    return {"mode": "default", **result}


@app.post("/api/jobs/{job_id}/categorize/ollama")
async def categorize_ollama_endpoint(job_id: str, payload: CategorizeRequest = Body(...)) -> Dict[str, object]:
    _ensure_duplicate_review_ready(job_id)
    merged_path = _resolve_job_merged_path(job_id)
    if store.count_active_ollama_events(job_id=job_id) > 0:
        raise HTTPException(status_code=409, detail="An Ollama categorization run is already queued or running for this job.")

    cfg = store.get_system_config()
    ollama_cfg = cfg.get("ollama", {}) if isinstance(cfg, dict) else {}

    ollama_url = str(ollama_cfg.get("url") or "").strip()
    ollama_model = str(ollama_cfg.get("model") or "").strip()
    enabled = bool(ollama_cfg.get("enabled"))
    if not enabled:
        raise HTTPException(status_code=400, detail="Ollama categorization is disabled in configuration.")
    if not ollama_url or not ollama_model:
        raise HTTPException(status_code=400, detail="Ollama URL or model is missing in configuration.")

    categories = payload.categories or list(ollama_cfg.get("default_categories") or [])
    categories = [str(item).strip() for item in categories if str(item).strip()]
    if not categories:
        raise HTTPException(status_code=400, detail="No categories available for Ollama categorization.")

    temperature_raw = ollama_cfg.get("temperature", 0.0)
    try:
        temperature = float(temperature_raw)
    except (TypeError, ValueError):
        temperature = 0.0
    batch_size_raw = payload.batch_size if payload.batch_size is not None else ollama_cfg.get("batch_size", 1)
    try:
        batch_size = max(1, min(200, int(batch_size_raw)))
    except (TypeError, ValueError):
        batch_size = 1

    default_auto_export = bool(ollama_cfg.get("auto_export_after_categorize"))
    auto_export = default_auto_export if payload.auto_export is None else bool(payload.auto_export)
    if auto_export:
        firefly_cfg = cfg.get("firefly", {}) if isinstance(cfg, dict) else {}
        importer_cfg = cfg.get("importer", {}) if isinstance(cfg, dict) else {}
        firefly_url = str((firefly_cfg.get("url") if isinstance(firefly_cfg, dict) else "") or "").strip()
        importer_json = str((importer_cfg.get("json_path") if isinstance(importer_cfg, dict) else "") or "").strip()
        if not firefly_url:
            raise HTTPException(status_code=400, detail="Auto-export requires Firefly URL in Configuration.")
        if not importer_json:
            raise HTTPException(status_code=400, detail="Auto-export requires importer JSON path in Configuration.")

    prompt_template = str(ollama_cfg.get("prompt_template") or "").strip()
    selected = [int(x) for x in payload.row_indices] if payload.row_indices is not None else None
    result = runner.start_ollama_categorization(
        job_id=job_id,
        merged_path=merged_path,
        row_indices=selected,
        overwrite=payload.overwrite,
        categories=categories,
        ollama_url=ollama_url,
        ollama_model=ollama_model,
        prompt_template=prompt_template,
        temperature=temperature,
        timeout_seconds=payload.timeout_seconds,
        batch_size=batch_size,
        auto_export=auto_export,
    )
    return {
        "mode": "ollama",
        "status": "queued",
        "categories": categories,
        "batch_size": batch_size,
        "auto_export": auto_export,
        **result,
    }


@app.post("/api/jobs/{job_id}/transactions/category")
async def update_transaction_category(job_id: str, payload: ManualCategoryUpdateRequest) -> Dict[str, object]:
    merged_path = _resolve_job_merged_path(job_id)
    with get_job_lock(job_id):
        result = set_category_by_row_index(
            path=merged_path,
            row_index=payload.merge_row_index,
            category=payload.category,
        )
    return {"status": "ok", **result}


@app.get("/api/ollama/events")
async def list_ollama_events(
    limit: int = 300,
    offset: int = 0,
    job_id: str = "",
    include_payload: bool = False,
    status_group: str = "all",
    sort_by: str = "id",
    sort_dir: str = "asc",
) -> Dict[str, object]:
    safe_limit = max(1, min(5000, int(limit)))
    safe_offset = max(0, int(offset))
    metrics_job_id = str(job_id or "").strip()
    if not metrics_job_id:
        metrics_job_id = store.get_latest_active_ollama_job_id()
    events = store.list_ollama_events(
        limit=safe_limit,
        offset=safe_offset,
        job_id=job_id,
        include_payload=bool(include_payload),
        status_group=status_group,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    total = store.count_ollama_events(job_id=job_id, status_group=status_group)
    metrics = store.get_ollama_queue_metrics(job_id=metrics_job_id)
    return {
        "events": events,
        "total": total,
        "offset": safe_offset,
        "limit": safe_limit,
        "has_more": (safe_offset + len(events)) < total,
        "metrics": metrics,
        "metrics_job_id": metrics_job_id,
    }


@app.get("/api/queues/summary")
async def get_queue_summary() -> Dict[str, object]:
    ollama_job_id = store.get_latest_active_ollama_job_id()
    if ollama_job_id:
        ollama_metrics = store.get_ollama_queue_metrics(job_id=ollama_job_id)
    else:
        ollama_metrics = {
            "total": 0,
            "queued": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "first_started_at": "",
            "last_finished_at": "",
        }
    active_export = store.get_latest_active_firefly_export()
    if active_export is None:
        firefly_metrics = {
            "total": 0,
            "queued": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "first_started_at": "",
            "last_finished_at": "",
        }
        firefly_export_id = ""
        firefly_job_id = ""
    else:
        firefly_export_id = str(active_export.get("id") or "")
        firefly_job_id = str(active_export.get("job_id") or "")
        firefly_metrics = store.get_firefly_export_queue_metrics(job_id=firefly_job_id, export_id=firefly_export_id)

    return {
        "ollama": {
            "job_id": ollama_job_id,
            "metrics": ollama_metrics,
        },
        "firefly_export": {
            "export_id": firefly_export_id,
            "job_id": firefly_job_id,
            "metrics": firefly_metrics,
        },
    }


@app.get("/api/ollama/events/{event_id}")
async def get_ollama_event(event_id: int) -> Dict[str, object]:
    event = store.get_ollama_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Ollama event not found.")
    return event


@app.post("/api/ollama/queues/stop")
async def stop_ollama_queue(payload: Optional[OllamaQueueStopRequest] = Body(default=None)) -> Dict[str, object]:
    body = payload or OllamaQueueStopRequest()
    job_id = str(body.job_id or "").strip() or store.get_latest_active_ollama_job_id()
    if not job_id:
        raise HTTPException(status_code=400, detail="No active Ollama queue to stop.")
    result = runner.stop_ollama_queue(job_id=job_id)
    return {"status": "stop_requested", **result}


@app.delete("/api/ollama/queues")
async def delete_ollama_queue(job_id: str = "", status_group: str = "all") -> Dict[str, object]:
    token = str(job_id or "").strip()
    if store.count_running_ollama_events(job_id=token) > 0:
        raise HTTPException(status_code=409, detail="Ollama queue has running items. Stop the queue first.")
    deleted = store.delete_ollama_events(job_id=token, status_group=status_group)
    return {"status": "deleted", "job_id": token, "status_group": status_group, "deleted": deleted}


@app.delete("/api/ollama/events/{event_id}")
async def delete_ollama_event(event_id: int) -> Dict[str, object]:
    event = store.get_ollama_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Ollama event not found.")
    if str(event.get("status") or "").strip() == "running":
        raise HTTPException(status_code=409, detail="Cannot delete a running Ollama event.")
    deleted = store.delete_ollama_event(event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ollama event not found.")
    return {"status": "deleted", "event_id": int(event_id)}


@app.post("/api/jobs/{job_id}/exports/firefly")
async def start_firefly_export(job_id: str, payload: Optional[FireflyExportRequest] = Body(default=None)) -> Dict[str, object]:
    payload = payload or FireflyExportRequest()
    _ensure_duplicate_review_ready(job_id)
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if str(job.get("status") or "").strip() != "completed":
        raise HTTPException(status_code=400, detail="Merge job must be completed before export.")
    artifacts = job.get("artifacts") or {}
    merged_raw = str(artifacts.get("merged_csv") or "").strip()
    if not merged_raw:
        raise HTTPException(status_code=400, detail="Merged CSV is not available for this job.")
    merged_path = Path(merged_raw)
    if not merged_path.exists():
        raise HTTPException(status_code=404, detail="Merged CSV does not exist.")
    _ensure_inside(merged_path, settings.jobs_dir / job_id)

    recent = store.list_firefly_exports(job_id=job_id, limit=1)
    if recent and str(recent[0].get("status") or "") in {"queued", "running"} and not payload.force:
        raise HTTPException(status_code=409, detail="A Firefly export is already queued or running for this job.")

    export_id = runner.start_firefly_export(job_id=job_id, options={"force": bool(payload.force)})
    return {"status": "queued", "export_id": export_id}


@app.post("/api/jobs/{job_id}/exports/firefly/{export_id}/stop")
async def stop_firefly_export_queue(job_id: str, export_id: str) -> Dict[str, object]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    export = store.get_firefly_export(export_id)
    if export is None or str(export.get("job_id") or "") != job_id:
        raise HTTPException(status_code=404, detail="Firefly export not found.")
    result = runner.stop_firefly_export(export_id=export_id)
    return {"status": "stop_requested", **result}


@app.delete("/api/jobs/{job_id}/exports/firefly")
async def delete_firefly_export_queues(job_id: str, status_group: str = "all") -> Dict[str, object]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    status_token = str(status_group or "all").strip().lower()
    includes_active = status_token in {"all", "queue", "queued", "active", ""}
    if includes_active and store.count_running_firefly_export_events(job_id=job_id) > 0:
        raise HTTPException(status_code=409, detail="Export queue has running items. Stop the queue first.")

    deleted = store.delete_firefly_exports(job_id=job_id, status_group=status_group)
    return {
        "status": "deleted",
        "job_id": job_id,
        "status_group": status_group,
        "deleted_exports": int(deleted.get("exports") or 0),
        "deleted_events": int(deleted.get("events") or 0),
    }


@app.delete("/api/jobs/{job_id}/exports/firefly/{export_id}")
async def delete_firefly_export_queue(job_id: str, export_id: str) -> Dict[str, object]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    export = store.get_firefly_export(export_id)
    if export is None or str(export.get("job_id") or "") != job_id:
        raise HTTPException(status_code=404, detail="Firefly export not found.")
    if store.count_running_firefly_export_events(export_id=export_id) > 0:
        raise HTTPException(status_code=409, detail="Export queue has running items. Stop the queue first.")
    deleted = store.delete_firefly_export(export_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Firefly export not found.")
    return {"status": "deleted", "export_id": export_id}


@app.delete("/api/jobs/{job_id}/exports/firefly/{export_id}/events")
async def delete_firefly_export_events(
    job_id: str,
    export_id: str,
    status_group: str = "all",
) -> Dict[str, object]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    export = store.get_firefly_export(export_id)
    if export is None or str(export.get("job_id") or "") != job_id:
        raise HTTPException(status_code=404, detail="Firefly export not found.")
    if store.count_running_firefly_export_events(export_id=export_id) > 0:
        raise HTTPException(status_code=409, detail="Export queue has running items. Stop the queue first.")
    deleted = store.delete_firefly_export_events(export_id=export_id, status_group=status_group)
    return {"status": "deleted", "export_id": export_id, "status_group": status_group, "deleted": deleted}


@app.post("/api/jobs/{job_id}/exports/firefly/{export_id}/retry-failed")
async def retry_failed_firefly_export_rows(
    job_id: str,
    export_id: str,
    payload: Optional[FireflyExportRequest] = Body(default=None),
) -> Dict[str, object]:
    payload = payload or FireflyExportRequest()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    source_export = store.get_firefly_export(export_id)
    if source_export is None or str(source_export.get("job_id") or "") != job_id:
        raise HTTPException(status_code=404, detail="Source Firefly export not found.")

    recent = store.list_firefly_exports(job_id=job_id, limit=1)
    if recent and str(recent[0].get("status") or "") in {"queued", "running"} and not payload.force:
        raise HTTPException(status_code=409, detail="A Firefly export is already queued or running for this job.")

    failed_row_indices = store.list_failed_firefly_export_row_indices(export_id=export_id)
    if not failed_row_indices:
        raise HTTPException(status_code=400, detail="No failed export rows found for retry.")

    new_export_id = runner.start_firefly_export(
        job_id=job_id,
        options={
            "force": bool(payload.force),
            "retry_failed_from_export_id": export_id,
            "row_indices": failed_row_indices,
        },
    )
    return {
        "status": "queued",
        "export_id": new_export_id,
        "source_export_id": export_id,
        "retry_rows": len(failed_row_indices),
    }


@app.get("/api/jobs/{job_id}/exports/firefly")
async def list_firefly_exports(job_id: str, limit: int = 50) -> Dict[str, object]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"exports": store.list_firefly_exports(job_id=job_id, limit=limit)}


@app.get("/api/jobs/{job_id}/exports/firefly/{export_id}")
async def get_firefly_export(job_id: str, export_id: str) -> Dict[str, object]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    export = store.get_firefly_export(export_id)
    if export is None or str(export.get("job_id") or "") != job_id:
        raise HTTPException(status_code=404, detail="Firefly export not found.")
    return export


@app.get("/api/jobs/{job_id}/exports/firefly/{export_id}/events")
async def list_firefly_export_events(
    job_id: str,
    export_id: str,
    limit: int = 200,
    offset: int = 0,
    include_payload: bool = False,
    status_group: str = "all",
    sort_by: str = "id",
    sort_dir: str = "asc",
) -> Dict[str, object]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    export = store.get_firefly_export(export_id)
    if export is None or str(export.get("job_id") or "") != job_id:
        raise HTTPException(status_code=404, detail="Firefly export not found.")

    safe_limit = max(1, min(5000, int(limit)))
    safe_offset = max(0, int(offset))
    events = store.list_firefly_export_events(
        limit=safe_limit,
        offset=safe_offset,
        job_id=job_id,
        export_id=export_id,
        include_payload=bool(include_payload),
        status_group=status_group,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    total = store.count_firefly_export_events(job_id=job_id, export_id=export_id, status_group=status_group)
    metrics = store.get_firefly_export_queue_metrics(job_id=job_id, export_id=export_id)
    return {
        "events": events,
        "total": total,
        "offset": safe_offset,
        "limit": safe_limit,
        "has_more": (safe_offset + len(events)) < total,
        "metrics": metrics,
    }


@app.get("/api/jobs/{job_id}/exports/firefly/events/{event_id}")
async def get_firefly_export_event(job_id: str, event_id: int) -> Dict[str, object]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    event = store.get_firefly_export_event(event_id)
    if event is None or str(event.get("job_id") or "") != job_id:
        raise HTTPException(status_code=404, detail="Firefly export event not found.")
    return event


@app.delete("/api/jobs/{job_id}/exports/firefly/events/{event_id}")
async def delete_firefly_export_event(job_id: str, event_id: int) -> Dict[str, object]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    event = store.get_firefly_export_event(event_id)
    if event is None or str(event.get("job_id") or "") != job_id:
        raise HTTPException(status_code=404, detail="Firefly export event not found.")
    if str(event.get("status") or "").strip() == "running":
        raise HTTPException(status_code=409, detail="Cannot delete a running export queue item.")
    deleted = store.delete_firefly_export_event(event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Firefly export event not found.")
    return {"status": "deleted", "event_id": int(event_id)}


@app.get("/api/jobs/{job_id}/artifacts/{artifact_key}")
async def download_artifact(job_id: str, artifact_key: str) -> FileResponse:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    artifacts = job.get("artifacts") or {}
    if artifact_key not in artifacts:
        raise HTTPException(status_code=404, detail="Artifact not found.")
    path = Path(artifacts[artifact_key])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Artifact file does not exist.")

    _ensure_inside(path, settings.jobs_dir / job_id)
    return FileResponse(path=path, filename=path.name, media_type="application/octet-stream")


@app.get("/api/config")
async def get_config() -> Dict[str, object]:
    return store.get_system_config()


@app.post("/api/config")
async def save_config(payload: SystemConfigPayload) -> Dict[str, object]:
    saved = store.set_system_config(payload.model_dump())
    return {"status": "saved", "config": saved}


@app.post("/api/config/reset")
async def reset_config(payload: Optional[ConfigResetRequest] = Body(default=None)) -> Dict[str, object]:
    body = payload or ConfigResetRequest()
    deleted_files = 0
    if body.clear_uploaded_importer_files:
        importer_dir = (settings.data_dir / "config" / "importer").resolve()
        if importer_dir.exists():
            _ensure_inside(importer_dir, settings.data_dir)
            for child in importer_dir.glob("*"):
                if child.is_file():
                    try:
                        child.unlink()
                        deleted_files += 1
                    except OSError:
                        pass
    saved = store.set_system_config({})
    return {
        "status": "reset",
        "deleted_importer_files": deleted_files,
        "config": saved,
    }


@app.post("/api/config/importer-json")
async def upload_importer_json(importer_file: UploadFile = File(...)) -> Dict[str, object]:
    raw_name = str(importer_file.filename or "").strip()
    safe_name = _safe_filename(raw_name or "import_config.json")
    if not safe_name.lower().endswith(".json"):
        safe_name = f"{Path(safe_name).stem}.json"

    raw_bytes = await importer_file.read()
    await importer_file.close()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded importer JSON file is empty.")
    try:
        text = raw_bytes.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Importer JSON must be UTF-8 encoded.") from exc

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Uploaded file is not valid JSON.") from exc

    target_dir = (settings.data_dir / "config" / "importer").resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    out_path = (target_dir / safe_name).resolve()
    _ensure_inside(out_path, settings.data_dir)
    out_path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")

    cfg = store.get_system_config()
    importer = cfg.get("importer", {}) if isinstance(cfg, dict) else {}
    if not isinstance(importer, dict):
        importer = {}
    importer["json_path"] = str(out_path)
    cfg["importer"] = importer
    saved = store.set_system_config(cfg)
    verification = _verify_importer_json_file(out_path)

    return {
        "status": "uploaded",
        "path": str(out_path),
        "verification": verification,
        "config": saved,
    }


@app.get("/api/config/importer-json/verify")
async def verify_importer_json(path: str = "") -> Dict[str, object]:
    target: Optional[Path] = None
    token = str(path or "").strip()
    if token:
        candidate = Path(token)
        if candidate.is_absolute():
            target = candidate.resolve()
        else:
            target = (settings.data_dir / candidate).resolve()
        _ensure_inside_allowed_dirs(target)
    else:
        cfg = store.get_system_config()
        importer = cfg.get("importer", {}) if isinstance(cfg, dict) else {}
        configured = str((importer.get("json_path") if isinstance(importer, dict) else "") or "").strip()
        if configured:
            target = Path(configured).resolve()
    if target is None:
        raise HTTPException(status_code=404, detail="No importer JSON path configured.")
    _ensure_inside_allowed_dirs(target)
    verification = _verify_importer_json_file(target)
    return {"status": "ok", "verification": verification}


@app.get("/api/config/export")
async def export_config(format: str = "yaml") -> Response:
    fmt = str(format or "yaml").strip().lower()
    cfg = store.get_system_config()
    if fmt == "json":
        content = json.dumps(cfg, indent=2, ensure_ascii=False)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="firefly_web_config.json"'},
        )
    if fmt in {"yaml", "yml"}:
        content = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=False)
        return Response(
            content=content,
            media_type="application/x-yaml",
            headers={"Content-Disposition": 'attachment; filename="firefly_web_config.yml"'},
        )
    raise HTTPException(status_code=400, detail="format must be json or yaml.")


@app.post("/api/config/import")
async def import_config(config_file: UploadFile = File(...)) -> Dict[str, object]:
    filename = str(config_file.filename or "").strip()
    raw_bytes = await config_file.read()
    await config_file.close()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded config file is empty.")
    try:
        text = raw_bytes.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Config file must be UTF-8 encoded.") from exc

    parsed: object
    ext = Path(filename).suffix.lower()
    try:
        if ext == ".json":
            parsed = json.loads(text)
        else:
            parsed = yaml.safe_load(text)
    except Exception:
        try:
            parsed = json.loads(text)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Unable to parse config file as YAML or JSON.") from exc

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="Config file must contain a JSON/YAML object.")

    normalized = _normalize_imported_config(parsed)
    saved = store.set_system_config(normalized)
    return {"status": "imported", "config": saved}


@app.post("/api/config/write-file")
async def write_config_file(payload: Optional[ConfigWriteFileRequest] = Body(default=None)) -> Dict[str, object]:
    body = payload or ConfigWriteFileRequest()
    fmt = str(body.format or "yaml").strip().lower()
    out_path = _resolve_config_output_path(body.path)
    cfg = store.get_system_config()
    if fmt == "json":
        text = json.dumps(cfg, indent=2, ensure_ascii=False)
    elif fmt in {"yaml", "yml"}:
        text = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=False)
    else:
        raise HTTPException(status_code=400, detail="format must be json or yaml.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return {
        "status": "written",
        "path": str(out_path),
        "format": fmt,
        "bytes": len(text.encode("utf-8")),
    }


def _normalize_imported_config(parsed: Dict[str, object]) -> Dict[str, object]:
    data = dict(parsed or {})
    if "global" in data and isinstance(data.get("global"), dict) and len(data) == 1:
        data = dict(data["global"])

    merge_keys = {"own_accounts", "account_aliases", "savings_accounts"}
    if "merge" not in data:
        merge_payload: Dict[str, object] = {}
        for key in merge_keys:
            if key in data:
                merge_payload[key] = data.pop(key)
        if merge_payload:
            data["merge"] = merge_payload
    return data


def _resolve_config_output_path(raw_path: str) -> Path:
    token = str(raw_path or "").strip() or "config/system_config.yml"
    candidate = Path(token)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (settings.data_dir / candidate).resolve()
    _ensure_inside(resolved, settings.data_dir)
    return resolved


def _verify_importer_json_file(path: Path) -> Dict[str, object]:
    target = path.resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail="Importer JSON file does not exist.")
    if not target.is_file():
        raise HTTPException(status_code=400, detail="Importer JSON path is not a regular file.")
    raw_bytes = target.read_bytes()
    try:
        text = raw_bytes.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Importer JSON file is not valid UTF-8.") from exc
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Importer JSON file contains invalid JSON.") from exc
    if isinstance(parsed, dict):
        keys = sorted(str(k) for k in parsed.keys())
    else:
        keys = []
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    sha_raw = hashlib.sha256(raw_bytes).hexdigest()
    sha_canonical = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "path": str(target),
        "bytes": len(raw_bytes),
        "sha256_raw": sha_raw,
        "sha256_canonical": sha_canonical,
        "valid_json": True,
        "top_level_key_count": len(keys),
        "top_level_keys": keys[:100],
    }


def _normalize_imported_merged_rows(
    rows: List[Dict[str, str]],
    fieldnames: List[str],
) -> tuple[List[Dict[str, str]], List[str]]:
    if not fieldnames:
        raise HTTPException(status_code=400, detail="Imported CSV is empty or has no header.")
    lowered = {str(name or "").strip().lower() for name in fieldnames}
    required = {"date", "amount", "description"}
    if not required.issubset(lowered):
        raise HTTPException(
            status_code=400,
            detail="Imported CSV must contain at least: date, amount, description.",
        )

    ordered_fields: List[str] = list(FIELDNAMES)
    for name in fieldnames:
        token = str(name or "").strip()
        if token and token not in ordered_fields:
            ordered_fields.append(token)

    field_lookup = {str(name or "").strip().lower(): str(name or "").strip() for name in fieldnames}
    normalized_rows: List[Dict[str, str]] = []
    for row in rows:
        out: Dict[str, str] = {}
        for field in ordered_fields:
            source_key = field_lookup.get(field.lower(), field)
            value = row.get(source_key, "")
            out[field] = str(value if value is not None else "")
        normalized_rows.append(out)
    return normalized_rows, ordered_fields


def _normalize_imported_duplicates_rows(
    rows: List[Dict[str, str]],
    fieldnames: List[str],
) -> tuple[List[Dict[str, str]], List[str]]:
    if not fieldnames:
        return [], list(DUPLICATE_FIELDNAMES)
    ordered_fields: List[str] = list(DUPLICATE_FIELDNAMES)
    for name in fieldnames:
        token = str(name or "").strip()
        if token and token not in ordered_fields:
            ordered_fields.append(token)
    field_lookup = {str(name or "").strip().lower(): str(name or "").strip() for name in fieldnames}
    normalized_rows: List[Dict[str, str]] = []
    for row in rows:
        out: Dict[str, str] = {}
        for field in ordered_fields:
            source_key = field_lookup.get(field.lower(), field)
            value = row.get(source_key, "")
            out[field] = str(value if value is not None else "")
        normalized_rows.append(out)
    return normalized_rows, ordered_fields


def _write_rows_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames or [])
        if fieldnames:
            writer.writeheader()
            for row in rows:
                writer.writerow({name: row.get(name, "") for name in fieldnames})


def _compute_duplicate_review_status(job_id: str) -> Dict[str, object]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    stats = job.get("stats") if isinstance(job.get("stats"), dict) else {}
    options = job.get("options") if isinstance(job.get("options"), dict) else {}
    review = options.get("duplicate_review") if isinstance(options.get("duplicate_review"), dict) else {}
    initial_duplicates = int(stats.get("duplicate_rows") or 0)

    pending_duplicates = 0
    duplicates_path_exists = False
    try:
        _, duplicates_path = _resolve_job_transaction_files(job_id)
        if duplicates_path is not None and duplicates_path.exists():
            duplicates_path_exists = True
            pending_duplicates = len(read_transactions(duplicates_path)[0])
    except HTTPException:
        pending_duplicates = max(0, initial_duplicates)

    restored_total = int(review.get("restored_rows_total") or 0)
    required = bool(pending_duplicates > 0 or initial_duplicates > 0 or review.get("required"))
    confirmed = bool(review.get("confirmed"))
    if pending_duplicates <= 0:
        required = False
        confirmed = True
    can_proceed = bool((not required) or confirmed)

    return {
        "job_id": job_id,
        "required": required,
        "confirmed": confirmed,
        "can_proceed": can_proceed,
        "initial_duplicates": initial_duplicates,
        "pending_duplicates": pending_duplicates,
        "duplicates_file_available": duplicates_path_exists,
        "restored_rows_total": restored_total,
        "confirmed_at": str(review.get("confirmed_at") or ""),
        "updated_at": str(review.get("updated_at") or ""),
    }


def _ensure_duplicate_review_ready(job_id: str) -> None:
    status = _compute_duplicate_review_status(job_id)
    if bool(status.get("can_proceed")):
        return
    pending = int(status.get("pending_duplicates") or 0)
    raise HTTPException(
        status_code=409,
        detail=(
            "Duplicate review is required before categorization/export. "
            f"Pending suspected duplicates: {pending}. Open the Duplicate Review tab, "
            "apply overrides if needed, and confirm the review."
        ),
    )


def _resolve_job_merged_path(job_id: str) -> Path:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    artifacts = job.get("artifacts") or {}
    raw = str(artifacts.get("merged_csv") or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Merged CSV is not available for this job.")
    path = Path(raw)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Merged CSV file does not exist.")
    _ensure_inside(path, settings.jobs_dir / job_id)
    return path


def _resolve_job_transaction_files(job_id: str) -> tuple[Path, Optional[Path]]:
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    artifacts = job.get("artifacts") or {}
    merged_raw = str(artifacts.get("merged_csv") or "").strip()
    if not merged_raw:
        raise HTTPException(status_code=400, detail="Merged CSV is not available for this job.")
    merged_path = Path(merged_raw)
    if not merged_path.exists():
        raise HTTPException(status_code=404, detail="Merged CSV file does not exist.")
    _ensure_inside(merged_path, settings.jobs_dir / job_id)

    duplicates_path: Optional[Path] = None
    duplicates_raw = str(artifacts.get("duplicates_csv") or "").strip()
    if duplicates_raw:
        candidate = Path(duplicates_raw)
        if candidate.exists():
            _ensure_inside(candidate, settings.jobs_dir / job_id)
            duplicates_path = candidate

    return merged_path, duplicates_path


def _build_effective_job_config(base_config_path: Path, job_dir: Path) -> Path:
    if not base_config_path.exists():
        raise HTTPException(status_code=400, detail="Config file does not exist.")
    try:
        loaded = yaml.safe_load(base_config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # pragma: no cover - malformed YAML
        raise HTTPException(status_code=400, detail="Config file is invalid or cannot be read.") from exc

    if not isinstance(loaded, dict):
        loaded = {}

    system_cfg = store.get_system_config()
    merge_cfg = system_cfg.get("merge", {}) if isinstance(system_cfg, dict) else {}
    if not isinstance(merge_cfg, dict):
        merge_cfg = {}

    own_accounts_raw = merge_cfg.get("own_accounts") or []
    if isinstance(own_accounts_raw, list):
        own_accounts = [str(item).strip() for item in own_accounts_raw if str(item).strip()]
        if own_accounts:
            loaded["own_accounts"] = own_accounts

    alias_raw = merge_cfg.get("account_aliases") or {}
    if isinstance(alias_raw, dict):
        alias_map = {str(k).strip(): str(v).strip() for k, v in alias_raw.items() if str(k).strip() and str(v).strip()}
        if alias_map:
            loaded["account_aliases"] = alias_map

    savings_raw = merge_cfg.get("savings_accounts") or {}
    if isinstance(savings_raw, dict):
        savings_out: Dict[str, object] = {}
        for key, value in savings_raw.items():
            sid = str(key).strip()
            if not sid:
                continue
            if isinstance(value, dict):
                item: Dict[str, str] = {}
                account = str(value.get("account") or "").strip()
                name = str(value.get("name") or "").strip()
                if account:
                    item["account"] = account
                if name:
                    item["name"] = name
                savings_out[sid] = item or {"account": sid}
            else:
                token = str(value).strip()
                if token:
                    savings_out[sid] = token
        if savings_out:
            loaded["savings_accounts"] = savings_out

    resolved_path = (job_dir / "effective_config.yml").resolve()
    resolved_path.write_text(yaml.safe_dump(loaded, sort_keys=False, allow_unicode=False), encoding="utf-8")
    return resolved_path
