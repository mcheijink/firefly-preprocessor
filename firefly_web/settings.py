"""Runtime settings for the web application."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    data_dir: Path
    jobs_dir: Path
    db_path: Path
    default_config_path: Path


def _to_resolved_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def load_settings() -> Settings:
    base_dir = Path(__file__).resolve().parents[1]
    data_dir_env = os.environ.get("FIREFLY_WEB_DATA_DIR")
    data_dir = _to_resolved_path(data_dir_env) if data_dir_env else (base_dir / "data").resolve()

    config_path_env = os.environ.get("APP_CONFIG_PATH")
    default_config_path = _to_resolved_path(config_path_env) if config_path_env else (base_dir / "config.yml").resolve()

    return Settings(
        base_dir=base_dir,
        data_dir=data_dir,
        jobs_dir=(data_dir / "jobs"),
        db_path=(data_dir / "app.db"),
        default_config_path=default_config_path,
    )

