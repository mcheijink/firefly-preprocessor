"""Transaction file helpers and lightweight analytics for merged outputs."""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

STRICT_PAIR_REASONS = {"strict_transfer_pair", "cross_file_transfer_pair"}


def read_transactions(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return rows, fieldnames


def write_transactions(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def list_transactions(path: Path, offset: int = 0, limit: int = 200) -> Dict[str, object]:
    rows, fieldnames = read_transactions(path)
    total = len(rows)
    safe_offset = max(0, int(offset))
    safe_limit = max(1, min(2000, int(limit)))
    selected = rows[safe_offset : safe_offset + safe_limit]
    payload_rows: List[Dict[str, str]] = []
    for idx, row in enumerate(selected, safe_offset + 1):
        entry = dict(row)
        entry["_row_index"] = str(idx)
        payload_rows.append(entry)
    return {
        "total": total,
        "offset": safe_offset,
        "limit": safe_limit,
        "fieldnames": fieldnames,
        "rows": payload_rows,
    }


def list_transaction_review(
    merged_path: Path,
    duplicates_path: Optional[Path] = None,
    offset: int = 0,
    limit: int = 200,
    include_duplicates: bool = True,
    decision: str = "all",
    search: str = "",
    source_file: str = "",
    sort_by: str = "date",
    sort_dir: str = "asc",
    summary_only: bool = False,
) -> Dict[str, object]:
    rows, baseline_counts = _build_review_rows(merged_path, duplicates_path if include_duplicates else None)
    overall_total = len(rows)
    source_files = sorted({(r.get("source_file") or "").strip() for r in rows if (r.get("source_file") or "").strip()})

    filtered = rows
    decision_token = (decision or "all").strip().lower()
    if decision_token in {"merged", "dropped"}:
        filtered = [r for r in filtered if _matches_decision_filter(r, decision_token)]

    source_token = (source_file or "").strip()
    if source_token:
        filtered = [r for r in filtered if (r.get("source_file") or "").strip() == source_token]

    query = (search or "").strip().lower()
    if query:
        filtered = [r for r in filtered if query in _row_search_text(r)]

    sorted_rows = _sort_review_rows(filtered, sort_by=sort_by, sort_dir=sort_dir)
    filtered_total = len(sorted_rows)

    safe_offset = max(0, int(offset))
    if int(limit) <= 0:
        selected = sorted_rows[safe_offset:]
        safe_limit = len(selected)
    else:
        safe_limit = max(1, min(200000, int(limit)))
        selected = sorted_rows[safe_offset : safe_offset + safe_limit]

    payload_rows: List[Dict[str, str]] = []
    for idx, row in enumerate(selected, safe_offset + 1):
        entry = _project_review_row_summary(row) if summary_only else dict(row)
        entry["_row_index"] = str(idx)
        payload_rows.append(entry)

    decision_counts = {
        "merged": sum(1 for r in filtered if (r.get("_decision") or "").strip().lower() == "merged"),
        "dropped": sum(_row_dropped_contribution(r) for r in filtered),
        "dropped_total": int(baseline_counts.get("dropped") or 0),
    }

    return {
        "overall_total": overall_total,
        "total": filtered_total,
        "offset": safe_offset,
        "limit": safe_limit,
        "rows": payload_rows,
        "source_files": source_files,
        "decision_counts": decision_counts,
    }


def get_transaction_review_detail(
    merged_path: Path,
    duplicates_path: Optional[Path],
    row_source: str,
    row_local_index: int,
) -> Optional[Dict[str, str]]:
    source_token = _normalize_row_source(row_source)
    idx = int(row_local_index or 0)
    if not source_token or idx <= 0:
        return None

    if source_token == "merged":
        rows, _ = read_transactions(merged_path)
        if idx > len(rows):
            return None
        item = dict(rows[idx - 1])
        item["_decision"] = "merged"
        item["_decision_reason"] = "kept"
        item["_row_source"] = "merged"
        item["_row_local_index"] = str(idx)
        item["_merge_row_index"] = str(idx)
        item.update(_project_review_row_summary(item))
        return item

    if source_token == "duplicates" and duplicates_path is not None and duplicates_path.exists():
        rows, _ = read_transactions(duplicates_path)
        if idx > len(rows):
            return None
        item = dict(rows[idx - 1])
        item["_decision"] = "dropped"
        item["_decision_reason"] = str(item.get("duplicate_reason") or "duplicate")
        item["_decision_reasoning"] = str(item.get("duplicate_reasoning") or "")
        item["_row_source"] = "duplicates"
        item["_row_local_index"] = str(idx)
        item["_merge_row_index"] = ""
        item.update(_project_review_row_summary(item))
        return item

    return None


def _normalize_token(value: str) -> str:
    return "".join((value or "").strip().upper().split())


def _normalize_description(value: str) -> str:
    raw = "".join(ch.lower() if ch.isalnum() else " " for ch in str(value or ""))
    return " ".join(raw.split())


def _amount_to_cents(value: str) -> int:
    raw = (value or "").strip().replace(",", ".")
    if not raw:
        return 0
    try:
        return int(round(float(raw) * 100))
    except ValueError:
        return 0


def _duplicate_match_rank(duplicate_row: Dict[str, str], kept_row: Dict[str, str], kept_idx: int) -> Tuple[int, int, int, int, int]:
    dup_src = _normalize_token(duplicate_row.get("source_account_number") or "")
    dup_dst = _normalize_token(duplicate_row.get("destination_account_number") or "")
    keep_src = _normalize_token(kept_row.get("source_account_number") or "")
    keep_dst = _normalize_token(kept_row.get("destination_account_number") or "")

    mirror_penalty = 0 if dup_src and dup_dst and dup_src == keep_dst and dup_dst == keep_src else 1

    dup_amt = abs(_amount_to_cents(duplicate_row.get("amount") or ""))
    keep_amt = abs(_amount_to_cents(kept_row.get("amount") or ""))
    amount_penalty = 0 if dup_amt and dup_amt == keep_amt else 1

    dup_date = str(duplicate_row.get("date") or "").strip()
    keep_date = str(kept_row.get("date") or "").strip()
    date_penalty = 0 if dup_date and dup_date == keep_date else 1

    dup_desc = _normalize_description(duplicate_row.get("description") or "")
    keep_desc = _normalize_description(kept_row.get("description") or "")
    if dup_desc and keep_desc:
        desc_penalty = 0 if dup_desc == keep_desc else 2
    elif dup_desc or keep_desc:
        desc_penalty = 1
    else:
        desc_penalty = 1

    return (mirror_penalty, amount_penalty, date_penalty, desc_penalty, int(kept_idx))


def _select_kept_candidate(
    duplicate_row: Dict[str, str],
    reason: str,
    by_external_id: Dict[str, List[Tuple[int, Dict[str, str]]]],
    by_pair_hash: Dict[str, List[Tuple[int, Dict[str, str]]]],
    used_strict_targets: set[int],
) -> Tuple[int, Dict[str, str]]:
    duplicate_of_external_id = str(duplicate_row.get("duplicate_of_external_id") or "").strip()
    pair_hash = str(duplicate_row.get("internal_pair_hash") or "").strip()
    strict_reason = str(reason or "").strip().lower() in STRICT_PAIR_REASONS

    def _pick(candidates: List[Tuple[int, Dict[str, str]]]) -> Tuple[int, Dict[str, str]]:
        if not candidates:
            return 0, {}
        if not strict_reason:
            return candidates[0]

        ranked: List[Tuple[Tuple[int, int, int, int, int], Tuple[int, Dict[str, str]]]] = []
        for kept_idx, kept_row in candidates:
            if int(kept_idx) in used_strict_targets:
                continue
            ranked.append(
                (
                    _duplicate_match_rank(duplicate_row, kept_row, int(kept_idx)),
                    (int(kept_idx), kept_row),
                )
            )
        if not ranked:
            return 0, {}
        ranked.sort(key=lambda item: item[0])
        return ranked[0][1]

    if duplicate_of_external_id:
        selected_idx, selected_row = _pick(by_external_id.get(duplicate_of_external_id, []))
        if selected_idx > 0:
            if strict_reason:
                used_strict_targets.add(int(selected_idx))
            return int(selected_idx), selected_row

    if pair_hash:
        selected_idx, selected_row = _pick(by_pair_hash.get(pair_hash, []))
        if selected_idx > 0:
            if strict_reason:
                used_strict_targets.add(int(selected_idx))
            return int(selected_idx), selected_row

    return 0, {}


def list_duplicate_suspects(
    merged_path: Path,
    duplicates_path: Optional[Path],
    offset: int = 0,
    limit: int = 100,
    search: str = "",
    source_file: str = "",
    sort_by: str = "date",
    sort_dir: str = "asc",
) -> Dict[str, object]:
    if duplicates_path is None or not duplicates_path.exists():
        return {
            "total": 0,
            "offset": 0,
            "limit": max(1, int(limit) if int(limit) > 0 else 100),
            "rows": [],
            "source_files": [],
            "reasons": {},
            "unmatched": 0,
        }

    merged_rows, _ = read_transactions(merged_path)
    dup_rows, _ = read_transactions(duplicates_path)

    by_external_id: Dict[str, List[Tuple[int, Dict[str, str]]]] = defaultdict(list)
    by_pair_hash: Dict[str, List[Tuple[int, Dict[str, str]]]] = defaultdict(list)
    for idx, row in enumerate(merged_rows, 1):
        ext = str(row.get("external_id") or "").strip()
        if ext:
            by_external_id[ext].append((idx, row))
        pair_hash = str(row.get("internal_pair_hash") or "").strip()
        if pair_hash:
            by_pair_hash[pair_hash].append((idx, row))

    suspects: List[Dict[str, Any]] = []
    reasons: Dict[str, int] = {}
    source_files_set = set()
    unmatched = 0
    used_strict_targets: set[int] = set()

    for idx, row in enumerate(dup_rows, 1):
        reason = str(row.get("duplicate_reason") or "duplicate").strip() or "duplicate"
        reasons[reason] = reasons.get(reason, 0) + 1
        source_file_val = str(row.get("source_file") or "").strip()
        if source_file_val:
            source_files_set.add(source_file_val)

        target_idx = 0
        target_row: Optional[Dict[str, str]] = None
        target_idx, selected_row = _select_kept_candidate(
            duplicate_row=row,
            reason=reason,
            by_external_id=by_external_id,
            by_pair_hash=by_pair_hash,
            used_strict_targets=used_strict_targets,
        )
        if target_idx > 0:
            target_row = selected_row

        if target_row is None:
            target_row = {}
            unmatched += 1

        suspects.append(
            {
                "id": f"d{idx}",
                "duplicate_row_index": idx,
                "duplicate_reason": reason,
                "duplicate_reasoning": str(row.get("duplicate_reasoning") or ""),
                "source_file": source_file_val,
                "duplicate_external_id": str(row.get("external_id") or ""),
                "duplicate_date": str(row.get("date") or ""),
                "duplicate_amount": str(row.get("amount") or ""),
                "duplicate_description": str(row.get("description") or ""),
                "duplicate_source_account": str(row.get("source_account") or ""),
                "duplicate_destination_account": str(row.get("destination_account") or ""),
                "duplicate_category": str(row.get("category") or ""),
                "kept_merge_row_index": target_idx,
                "kept_external_id": str(target_row.get("external_id") or ""),
                "kept_date": str(target_row.get("date") or ""),
                "kept_amount": str(target_row.get("amount") or ""),
                "kept_description": str(target_row.get("description") or ""),
                "kept_source_account": str(target_row.get("source_account") or ""),
                "kept_destination_account": str(target_row.get("destination_account") or ""),
                "kept_category": str(target_row.get("category") or ""),
                "_duplicate_row_source": "duplicates",
                "_duplicate_row_local_index": str(idx),
                "_kept_row_source": "merged" if target_idx > 0 else "",
                "_kept_row_local_index": str(target_idx) if target_idx > 0 else "",
                "_has_match": "1" if target_idx > 0 else "0",
            }
        )

    source_token = (source_file or "").strip()
    filtered = suspects
    if source_token:
        filtered = [item for item in filtered if str(item.get("source_file") or "") == source_token]

    query = (search or "").strip().lower()
    if query:
        filtered = [item for item in filtered if query in _duplicate_suspect_search_text(item)]

    sorted_rows = _sort_duplicate_suspects(filtered, sort_by=sort_by, sort_dir=sort_dir)
    safe_offset = max(0, int(offset))
    if int(limit) <= 0:
        selected = sorted_rows[safe_offset:]
        safe_limit = len(selected)
    else:
        safe_limit = max(1, min(1000, int(limit)))
        selected = sorted_rows[safe_offset : safe_offset + safe_limit]

    return {
        "total": len(sorted_rows),
        "offset": safe_offset,
        "limit": safe_limit,
        "rows": selected,
        "source_files": sorted(source_files_set),
        "reasons": reasons,
        "unmatched": unmatched,
    }


def restore_duplicate_rows(
    merged_path: Path,
    duplicates_path: Optional[Path],
    duplicate_row_indices: Iterable[int],
) -> Dict[str, int]:
    if duplicates_path is None or not duplicates_path.exists():
        return {"restored_rows": 0, "merged_rows": len(read_transactions(merged_path)[0]), "remaining_duplicates": 0}

    merged_rows, merged_fieldnames = read_transactions(merged_path)
    dup_rows, dup_fieldnames = read_transactions(duplicates_path)
    if not merged_fieldnames:
        return {"restored_rows": 0, "merged_rows": len(merged_rows), "remaining_duplicates": len(dup_rows)}

    chosen: List[int] = []
    total_dups = len(dup_rows)
    for raw in duplicate_row_indices or []:
        idx = int(raw)
        if 1 <= idx <= total_dups:
            chosen.append(idx)
    unique_indices = sorted(set(chosen))
    if not unique_indices:
        return {"restored_rows": 0, "merged_rows": len(merged_rows), "remaining_duplicates": len(dup_rows)}

    restored_items: List[Dict[str, str]] = []
    for idx in unique_indices:
        row = dup_rows[idx - 1]
        normalized: Dict[str, str] = {}
        for field in merged_fieldnames:
            normalized[field] = str(row.get(field, "") or "")
        restored_items.append(normalized)

    for idx in sorted(unique_indices, reverse=True):
        del dup_rows[idx - 1]

    merged_rows.extend(restored_items)
    merged_rows = sorted(
        merged_rows,
        key=lambda row: (
            _date_sort_key(str(row.get("date") or "")),
            str(row.get("external_id") or ""),
            str(row.get("description") or ""),
        ),
    )

    write_transactions(merged_path, merged_rows, merged_fieldnames)
    dup_fields = dup_fieldnames if dup_fieldnames else _infer_fieldnames(dup_rows)
    if dup_fields:
        write_transactions(duplicates_path, dup_rows, dup_fields)
    else:
        duplicates_path.write_text("", encoding="utf-8")

    return {
        "restored_rows": len(restored_items),
        "merged_rows": len(merged_rows),
        "remaining_duplicates": len(dup_rows),
    }


def apply_categories(
    path: Path,
    row_indices: Optional[Iterable[int]],
    assign_category,
    overwrite: bool = False,
) -> Dict[str, int]:
    rows, fieldnames = read_transactions(path)
    selected = set(int(x) for x in row_indices) if row_indices is not None else None
    updated = 0
    skipped = 0
    for idx, row in enumerate(rows, 1):
        if selected is not None and idx not in selected:
            skipped += 1
            continue
        existing = (row.get("category") or "").strip()
        if existing and not overwrite:
            skipped += 1
            continue
        category = (assign_category(row) or "").strip()
        if not category:
            skipped += 1
            continue
        row["category"] = category
        updated += 1
    write_transactions(path, rows, fieldnames)
    return {"updated": updated, "skipped": skipped, "total_rows": len(rows)}


def set_category_by_row_index(path: Path, row_index: int, category: str) -> Dict[str, int]:
    rows, fieldnames = read_transactions(path)
    idx = int(row_index)
    if idx <= 0 or idx > len(rows):
        return {"updated": 0, "skipped": 1, "total_rows": len(rows)}
    rows[idx - 1]["category"] = (category or "").strip()
    write_transactions(path, rows, fieldnames)
    return {"updated": 1, "skipped": 0, "total_rows": len(rows)}


def build_balance_series(path: Path) -> Dict[str, object]:
    rows, _ = read_transactions(path)
    points_by_account: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    running_balances: Dict[str, float] = defaultdict(float)

    ordered = sorted(rows, key=lambda r: ((r.get("date") or ""), (r.get("external_id") or "")))
    for row in ordered:
        date = (row.get("date") or "").strip()
        if not date:
            continue
        account = (row.get("source_account_number") or "").strip()
        if not account:
            continue

        amount = _to_float(row.get("amount") or "")
        assumed_balance = row.get("assumed_balance") or ""
        if assumed_balance.strip():
            running = _to_float(assumed_balance)
        else:
            running_balances[account] += amount
            running = running_balances[account]
        running_balances[account] = running
        points_by_account[account].append((date, running))

    series = []
    for account, points in sorted(points_by_account.items()):
        compressed = _compress_by_date(points)
        series.append(
            {
                "account": account,
                "points": [{"date": dt, "balance": round(val, 2)} for dt, val in compressed],
            }
        )
    return {"series": series}


def _compress_by_date(points: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
    if not points:
        return []
    last_by_date: Dict[str, float] = {}
    for date, value in points:
        last_by_date[date] = value
    ordered_dates = sorted(last_by_date.keys(), key=_date_sort_key)
    return [(d, last_by_date[d]) for d in ordered_dates]


def _date_sort_key(raw: str) -> datetime:
    text = (raw or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.max


def _to_float(value: str) -> float:
    raw = (value or "").strip().replace(",", ".")
    if not raw:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _build_review_rows(merged_path: Path, duplicates_path: Optional[Path]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    merged_rows, _ = read_transactions(merged_path)
    out: List[Dict[str, Any]] = []
    by_external_id: Dict[str, List[Tuple[int, Dict[str, Any]]]] = defaultdict(list)
    by_pair_hash: Dict[str, List[Tuple[int, Dict[str, Any]]]] = defaultdict(list)
    for idx, row in enumerate(merged_rows, 1):
        item = dict(row)
        item["_decision"] = "merged"
        item["_decision_reason"] = "kept"
        item["_row_source"] = "merged"
        item["_row_local_index"] = str(idx)
        item["_merge_row_index"] = str(idx)
        item["_dropped_matches"] = []
        item["_dropped_count"] = "0"
        out.append(item)
        external_id = (item.get("external_id") or "").strip()
        if external_id:
            by_external_id[external_id].append((idx, item))
        pair_hash = (item.get("internal_pair_hash") or "").strip()
        if pair_hash:
            by_pair_hash[pair_hash].append((idx, item))

    dropped_total = 0
    used_strict_targets: set[int] = set()
    if duplicates_path is not None and duplicates_path.exists():
        dup_rows, _ = read_transactions(duplicates_path)
        for idx, row in enumerate(dup_rows, 1):
            item = dict(row)
            item["_decision"] = "dropped"
            item["_decision_reason"] = str(item.get("duplicate_reason") or "duplicate")
            item["_decision_reasoning"] = str(item.get("duplicate_reasoning") or "")
            item["_row_source"] = "duplicates"
            item["_row_local_index"] = str(idx)
            item["_merge_row_index"] = ""
            item["_dropped_matches"] = []
            item["_dropped_count"] = "0"
            dropped_total += 1

            attached = False
            reason = str(item.get("duplicate_reason") or "duplicate").strip() or "duplicate"
            target_idx, target_selected = _select_kept_candidate(
                duplicate_row=item,
                reason=reason,
                by_external_id=by_external_id,
                by_pair_hash=by_pair_hash,
                used_strict_targets=used_strict_targets,
            )
            target = target_selected if target_idx > 0 else None

            if target is not None:
                match = _project_review_row_summary(item)
                match["_paired_merged_id"] = str(target.get("id") or target.get("external_id") or "")
                dropped_matches = target.get("_dropped_matches")
                if not isinstance(dropped_matches, list):
                    dropped_matches = []
                    target["_dropped_matches"] = dropped_matches
                dropped_matches.append(match)
                target["_dropped_count"] = str(len(dropped_matches))
                attached = True

            if not attached:
                out.append(item)

    return out, {"merged": len(merged_rows), "dropped": dropped_total}


def _project_review_row_summary(row: Dict[str, str]) -> Dict[str, str]:
    decision = str(row.get("_decision") or "merged").strip().lower()
    local_idx = _to_int(row.get("_row_local_index") or "0")
    merge_idx = _to_int(row.get("_merge_row_index") or "0")
    public_id = str(merge_idx) if decision == "merged" and merge_idx > 0 else f"d{max(0, local_idx)}"
    return {
        "id": public_id,
        "date": row.get("date", ""),
        "amount": row.get("amount", ""),
        "external_id": row.get("external_id", ""),
        "source_file": row.get("source_file", ""),
        "category": row.get("category", ""),
        "description": row.get("description", ""),
        "source_account": row.get("source_account", ""),
        "destination_account": row.get("destination_account", ""),
        "duplicate_reason": row.get("duplicate_reason", ""),
        "duplicate_reasoning": row.get("duplicate_reasoning", ""),
        "duplicate_of_external_id": row.get("duplicate_of_external_id", ""),
        "_decision": row.get("_decision", ""),
        "_decision_reason": row.get("_decision_reason", ""),
        "_decision_reasoning": row.get("_decision_reasoning", ""),
        "_row_source": row.get("_row_source", ""),
        "_row_local_index": row.get("_row_local_index", ""),
        "_merge_row_index": row.get("_merge_row_index", ""),
        "_dropped_count": str(row.get("_dropped_count") or "0"),
        "_dropped_matches": row.get("_dropped_matches", []) if isinstance(row.get("_dropped_matches"), list) else [],
    }


def _normalize_row_source(raw: str) -> str:
    token = (raw or "").strip().lower()
    if token in {"merged", "m"}:
        return "merged"
    if token in {"duplicates", "duplicate", "dropped", "d"}:
        return "duplicates"
    return ""


def _row_search_text(row: Dict[str, str]) -> str:
    parts = [
        row.get("date", ""),
        row.get("amount", ""),
        row.get("description", ""),
        row.get("source_account", ""),
        row.get("source_account_number", ""),
        row.get("destination_account", ""),
        row.get("destination_account_number", ""),
        row.get("type", ""),
        row.get("external_id", ""),
        row.get("currency_code", ""),
        row.get("notes", ""),
        row.get("category", ""),
        row.get("tags", ""),
        row.get("source_file", ""),
        row.get("duplicate_reason", ""),
        row.get("duplicate_reasoning", ""),
        row.get("duplicate_of_external_id", ""),
        row.get("_decision", ""),
        row.get("_decision_reason", ""),
        row.get("_decision_reasoning", ""),
    ]
    dropped_matches = row.get("_dropped_matches")
    if isinstance(dropped_matches, list):
        for match in dropped_matches:
            if not isinstance(match, dict):
                continue
            parts.extend(
                [
                    str(match.get("id") or ""),
                    str(match.get("date") or ""),
                    str(match.get("amount") or ""),
                    str(match.get("description") or ""),
                    str(match.get("external_id") or ""),
                    str(match.get("_decision_reason") or ""),
                    str(match.get("_decision_reasoning") or ""),
                ]
            )
    return " ".join((p or "").strip().lower() for p in parts)


def _sort_review_rows(rows: List[Dict[str, str]], sort_by: str, sort_dir: str) -> List[Dict[str, str]]:
    token = (sort_by or "date").strip().lower()
    reverse = (sort_dir or "asc").strip().lower() == "desc"

    def _str_key(field: str):
        return lambda row: (row.get(field) or "").strip().lower()

    key_fn = {
        "id": _review_sort_id,
        "date": lambda row: _date_sort_key(row.get("date") or ""),
        "amount": lambda row: _to_float(row.get("amount") or ""),
        "description": _str_key("description"),
        "source_account": _str_key("source_account"),
        "destination_account": _str_key("destination_account"),
        "source_file": _str_key("source_file"),
        "external_id": _str_key("external_id"),
        "category": _str_key("category"),
        "type": _str_key("type"),
        "decision": _str_key("_decision"),
        "reason": _str_key("_decision_reason"),
    }.get(token, lambda row: _date_sort_key(row.get("date") or ""))

    return sorted(rows, key=key_fn, reverse=reverse)


def _duplicate_suspect_search_text(item: Dict[str, Any]) -> str:
    parts = [
        item.get("id", ""),
        item.get("duplicate_reason", ""),
        item.get("duplicate_reasoning", ""),
        item.get("source_file", ""),
        item.get("duplicate_external_id", ""),
        item.get("duplicate_date", ""),
        item.get("duplicate_amount", ""),
        item.get("duplicate_description", ""),
        item.get("duplicate_source_account", ""),
        item.get("duplicate_destination_account", ""),
        item.get("kept_external_id", ""),
        item.get("kept_date", ""),
        item.get("kept_amount", ""),
        item.get("kept_description", ""),
        item.get("kept_source_account", ""),
        item.get("kept_destination_account", ""),
    ]
    return " ".join(str(part or "").strip().lower() for part in parts)


def _sort_duplicate_suspects(rows: List[Dict[str, Any]], sort_by: str, sort_dir: str) -> List[Dict[str, Any]]:
    token = (sort_by or "date").strip().lower()
    reverse = (sort_dir or "asc").strip().lower() == "desc"

    def _str_key(field: str):
        return lambda row: str(row.get(field) or "").strip().lower()

    key_fn = {
        "id": lambda row: int(row.get("duplicate_row_index") or 0),
        "reason": _str_key("duplicate_reason"),
        "reasoning": _str_key("duplicate_reasoning"),
        "date": lambda row: _date_sort_key(str(row.get("duplicate_date") or "")),
        "amount": lambda row: _to_float(str(row.get("duplicate_amount") or "")),
        "description": _str_key("duplicate_description"),
        "source_account": _str_key("duplicate_source_account"),
        "destination_account": _str_key("duplicate_destination_account"),
        "source_file": _str_key("source_file"),
        "kept_id": lambda row: int(row.get("kept_merge_row_index") or 0),
        "kept_date": lambda row: _date_sort_key(str(row.get("kept_date") or "")),
        "kept_amount": lambda row: _to_float(str(row.get("kept_amount") or "")),
    }.get(token, lambda row: _date_sort_key(str(row.get("duplicate_date") or "")))
    return sorted(rows, key=key_fn, reverse=reverse)


def _infer_fieldnames(rows: List[Dict[str, str]]) -> List[str]:
    ordered: List[str] = []
    seen = set()
    for row in rows:
        for key in row.keys():
            token = str(key or "")
            if token and token not in seen:
                seen.add(token)
                ordered.append(token)
    return ordered


def _review_sort_id(row: Dict[str, str]) -> Tuple[int, int]:
    decision = (row.get("_decision") or "").strip().lower()
    if decision == "merged":
        idx = _to_int(row.get("_merge_row_index") or "0")
        return (0, idx)
    idx = _to_int(row.get("_row_local_index") or "0")
    return (1, idx)


def _matches_decision_filter(row: Dict[str, Any], decision: str) -> bool:
    token = (decision or "").strip().lower()
    row_decision = (row.get("_decision") or "").strip().lower()
    if token == "merged":
        return row_decision == "merged"
    if token == "dropped":
        if row_decision == "dropped":
            return True
        return _row_dropped_count(row) > 0
    return True


def _row_dropped_count(row: Dict[str, Any]) -> int:
    if (row.get("_decision") or "").strip().lower() == "dropped":
        return 1
    dropped_matches = row.get("_dropped_matches")
    if isinstance(dropped_matches, list):
        return len(dropped_matches)
    return _to_int(str(row.get("_dropped_count") or "0"))


def _row_dropped_contribution(row: Dict[str, Any]) -> int:
    return _row_dropped_count(row)


def _to_int(value: str) -> int:
    raw = (value or "").strip()
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError:
        return 0
