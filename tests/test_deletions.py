import importlib


def test_dedupe_module_gone():
    found = importlib.util.find_spec("firefly_web.dedupe")
    assert found is None


def test_store_has_no_fingerprint_api(tmp_store):
    assert not hasattr(tmp_store, "lookup_fingerprint")
    assert not hasattr(tmp_store, "insert_fingerprint")


def test_fingerprints_table_not_created(tmp_store):
    import sqlite3
    with sqlite3.connect(tmp_store.db_path) as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "fingerprints" not in names
