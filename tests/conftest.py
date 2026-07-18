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
