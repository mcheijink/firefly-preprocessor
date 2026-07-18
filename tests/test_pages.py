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


@pytest.mark.parametrize("path", PAGES)
def test_pages_render(client, path):
    assert client.get(path).status_code == 200
