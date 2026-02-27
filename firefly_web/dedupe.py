"""Cross-run dedupe helpers and transaction fingerprinting."""

from __future__ import annotations

import hashlib
from typing import Dict, List, Tuple

from .store import JobStore


def _normalize_token(value: str) -> str:
    return "".join((value or "").strip().upper().split())


def _normalize_text(value: str) -> str:
    compact = " ".join((value or "").strip().split())
    return compact.lower()


def _amount_to_cents(value: str) -> int:
    raw = (value or "").strip().replace(",", ".")
    if not raw:
        return 0
    try:
        return int(round(float(raw) * 100))
    except ValueError:
        return 0


def row_fingerprint(row: Dict[str, str]) -> str:
    payload = "|".join(
        [
            (row.get("date") or "").strip(),
            str(_amount_to_cents(row.get("amount") or "")),
            _normalize_token(row.get("source_account_number") or ""),
            _normalize_token(row.get("destination_account_number") or ""),
            _normalize_text(row.get("description") or ""),
            _normalize_token(row.get("type") or ""),
            _normalize_token(row.get("currency_code") or ""),
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _is_internal_pair_mirror(existing: Dict[str, str], candidate: Dict[str, str]) -> bool:
    if (existing.get("type") or "").strip().lower() != "transfer":
        return False
    if (candidate.get("type") or "").strip().lower() != "transfer":
        return False

    hash_existing = (existing.get("internal_pair_hash") or "").strip()
    hash_candidate = (candidate.get("internal_pair_hash") or "").strip()
    if not hash_existing or hash_existing != hash_candidate:
        return False

    src_a = _normalize_token(existing.get("source_account_number") or "")
    dst_a = _normalize_token(existing.get("destination_account_number") or "")
    src_b = _normalize_token(candidate.get("source_account_number") or "")
    dst_b = _normalize_token(candidate.get("destination_account_number") or "")
    if not src_a or not dst_a or not src_b or not dst_b:
        return False
    if src_a != dst_b or dst_a != src_b:
        return False

    amount_a = _amount_to_cents(existing.get("amount") or "")
    amount_b = _amount_to_cents(candidate.get("amount") or "")
    return amount_a == -amount_b and amount_a != 0


def _apply_internal_transfer_pair_dedupe(rows: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    kept: List[Dict[str, str]] = []
    duplicates: List[Dict[str, str]] = []
    buckets: Dict[str, List[Dict[str, str]]] = {}

    for row in rows:
        pair_hash = (row.get("internal_pair_hash") or "").strip()
        if not pair_hash:
            kept.append(row)
            continue

        existing_entries = buckets.setdefault(pair_hash, [])
        mirror = next((item for item in existing_entries if _is_internal_pair_mirror(item, row)), None)
        if mirror is None:
            existing_entries.append(row)
            kept.append(row)
            continue

        duplicate_row = dict(row)
        duplicate_row["duplicate_reason"] = "internal_pair_duplicate"
        duplicate_row["duplicate_reasoning"] = (
            "Matched mirrored internal transfer pair by internal_pair_hash with opposite sign amount and reversed accounts."
        )
        duplicate_row["duplicate_of_external_id"] = mirror.get("external_id", "")
        duplicates.append(duplicate_row)

    return kept, duplicates


def apply_global_dedupe(
    rows: List[Dict[str, str]],
    store: JobStore,
    job_id: str,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], int]:
    prefiltered_rows, internal_duplicates = _apply_internal_transfer_pair_dedupe(rows)

    kept: List[Dict[str, str]] = []
    duplicates: List[Dict[str, str]] = list(internal_duplicates)
    pending: Dict[str, str] = {}

    for row in prefiltered_rows:
        fingerprint = row_fingerprint(row)
        already_seen_external_id = store.lookup_fingerprint(fingerprint)
        if already_seen_external_id is not None:
            duplicate_row = dict(row)
            duplicate_row["duplicate_reason"] = "global_duplicate"
            duplicate_row["duplicate_reasoning"] = (
                "Matched transaction fingerprint from a previous job (cross-run fingerprint dedupe)."
            )
            duplicate_row["duplicate_of_external_id"] = already_seen_external_id
            duplicates.append(duplicate_row)
            continue

        if fingerprint in pending:
            duplicate_row = dict(row)
            duplicate_row["duplicate_reason"] = "global_duplicate_same_job"
            duplicate_row["duplicate_reasoning"] = (
                "Matched transaction fingerprint already seen in the current job."
            )
            duplicate_row["duplicate_of_external_id"] = pending[fingerprint]
            duplicates.append(duplicate_row)
            continue

        pending[fingerprint] = row.get("external_id", "")
        kept.append(row)

    inserted = 0
    for fingerprint, external_id in pending.items():
        if store.insert_fingerprint(fingerprint, external_id, job_id):
            inserted += 1

    return kept, duplicates, inserted
