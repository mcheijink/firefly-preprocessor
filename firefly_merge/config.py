"""Configuration helpers."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
except Exception:  # pragma: no cover - fallback when PyYAML missing
    yaml = None


DEFAULT_CONFIG = {
    "own_accounts": [],
    "currency_code": "EUR",
    "account_aliases": {},
    "timezone": "Europe/Berlin",
    "savings_accounts": {},
    "ai": {
        "enabled": False,
        "ollama_url": "http://localhost:11434",
        "model": "gpt-oss:20b",
        "temperature": 0.0,
        "preferred_categories": [],
    },
    "firefly": {
        "enabled": False,
        "url": "",
        "secret": "",
        "token": "",
        "json_config": "",
        "timeout": 30,
        "batch_size": 50,
    },
    "importer": {},
}


def load_config(path: Optional[str]) -> dict:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg.setdefault("importer", {})
    cfg.setdefault("firefly", {})
    cfg.setdefault("savings_accounts", {})

    if path:
        if yaml is None:
            print("WARNING: PyYAML not installed. Ignoring -c/--config.", file=sys.stderr)
        else:
            data = Path(path).read_text(encoding="utf-8")
            loaded = yaml.safe_load(data) or {}
            ai_loaded = (loaded or {}).get("ai") or {}
            importer_loaded = (loaded or {}).get("importer") or {}
            firefly_loaded = (loaded or {}).get("firefly") or {}
            savings_loaded = (loaded or {}).get("savings_accounts") or {}
            loaded = {k: v for k, v in loaded.items() if k not in {"ai", "importer", "firefly", "savings_accounts"}}
            cfg.update(loaded)
            cfg["ai"].update(ai_loaded)
            cfg["importer"].update(importer_loaded)
            cfg["firefly"].update(firefly_loaded)
            cfg["savings_accounts"].update(savings_loaded)
            if not cfg["firefly"].get("batch_size"):
                cfg["firefly"]["batch_size"] = 50
    return cfg


__all__ = ["load_config", "DEFAULT_CONFIG"]
