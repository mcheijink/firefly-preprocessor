"""Runtime settings for the web application."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Default upload limit: 200 MB
_DEFAULT_MAX_UPLOAD_BYTES = 200 * 1024 * 1024


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    data_dir: Path
    jobs_dir: Path
    db_path: Path
    default_config_path: Path
    # Parent directory of default_config_path; used as a second allowed root
    # for file-path validation (e.g. /config volume in Docker).
    config_dir: Path
    # If non-empty, HTTP Basic Auth is required (password = this value).
    app_secret: str
    # Maximum accepted Content-Length for uploads (0 = unlimited).
    max_upload_bytes: int


def _to_resolved_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def load_settings() -> Settings:
    base_dir = Path(__file__).resolve().parents[1]
    data_dir_env = os.environ.get("FIREFLY_WEB_DATA_DIR")
    data_dir = _to_resolved_path(data_dir_env) if data_dir_env else (base_dir / "data").resolve()

    config_path_env = os.environ.get("APP_CONFIG_PATH")
    default_config_path = _to_resolved_path(config_path_env) if config_path_env else (base_dir / "config.yml").resolve()

    app_secret = os.environ.get("APP_SECRET", "").strip()

    try:
        max_upload_bytes = int(os.environ.get("MAX_UPLOAD_BYTES", str(_DEFAULT_MAX_UPLOAD_BYTES)))
    except ValueError:
        max_upload_bytes = _DEFAULT_MAX_UPLOAD_BYTES

    return Settings(
        base_dir=base_dir,
        data_dir=data_dir,
        jobs_dir=(data_dir / "jobs"),
        db_path=(data_dir / "app.db"),
        default_config_path=default_config_path,
        config_dir=default_config_path.parent,
        app_secret=app_secret,
        max_upload_bytes=max_upload_bytes,
    )

