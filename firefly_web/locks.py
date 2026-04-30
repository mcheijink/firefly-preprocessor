"""Per-job threading locks for safe CSV read-modify-write operations."""

from __future__ import annotations

import threading
from typing import Dict


_registry: Dict[str, threading.Lock] = {}
_registry_lock = threading.Lock()


def get_job_lock(job_id: str) -> threading.Lock:
    """Return (creating if necessary) the per-job lock for CSV mutations."""
    with _registry_lock:
        if job_id not in _registry:
            _registry[job_id] = threading.Lock()
        return _registry[job_id]
