"""Command-line interface for merging bank exports."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import html
import re
import unicodedata
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import load_config
from .parsers import (
    is_bunq_header,
    is_ing_header,
    parse_bunq_mt940,
    parse_bunq,
    parse_ing,
)
from .savings import build_savings_map
from .utils import csv_reader_autodetect, parse_date, normalize_decimal


FIELDNAMES = [
    "date",
    "amount",
    "assumed_balance",
    "reported_balance",
    "currency_code",
    "description",
    "source_account",
    "source_account_number",
    "destination_account",
    "destination_account_number",
    "type",
    "external_id",
    "notes",
    "category",
    "tags",
    "source_file",
    "internal_pair_hash",
]

DUPLICATE_FIELDNAMES = FIELDNAMES + ["duplicate_reason", "duplicate_reasoning", "duplicate_of_external_id"]
MT940_SUFFIXES = {".mt940", ".sta", ".940"}
SUPPORTED_INPUT_SUFFIXES = {".csv"} | MT940_SUFFIXES


def write_transactions(path: Path, rows: List[Dict[str, str]], fieldnames: Optional[List[str]] = None) -> None:
    fieldnames = fieldnames or FIELDNAMES
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def archive_previous_exports(outdir: Path, upcoming: Path, vlog) -> None:
    archive_dir = outdir / "old"
    archive_dir.mkdir(parents=True, exist_ok=True)
    try:
        upcoming_resolved = upcoming.resolve(strict=False)
    except TypeError:
        upcoming_resolved = upcoming
    for existing in outdir.glob("*.csv"):
        if not existing.is_file():
            continue
        if not existing.name.startswith("merged") or "_upload_" in existing.name:
            continue
        try:
            if existing.resolve(strict=False) == upcoming_resolved:
                continue
        except FileNotFoundError:
            pass
        dest = archive_dir / existing.name
        counter = 1
        while dest.exists():
            dest = archive_dir / f"{existing.stem}_{counter}{existing.suffix}"
            counter += 1
        existing.replace(dest)
        vlog(f"[archive] moved {existing.name} -> {dest.relative_to(outdir)}")

def chunked_rows(rows: List[Dict[str, str]], size: int) -> List[List[Dict[str, str]]]:
    if size <= 0:
        size = 50
    return [rows[i : i + size] for i in range(0, len(rows), size)]


def upload_batches(final_out_path: Path, rows: List[Dict[str, str]], firefly_cfg: dict, config_dir: Optional[Path], vlog) -> List[str]:
    batch_size = firefly_cfg.get("batch_size") or 50
    try:
        batch_size = max(1, int(batch_size))
    except (TypeError, ValueError):
        batch_size = 50

    batches = chunked_rows(rows, batch_size)
    total = len(batches)
    summaries: List[str] = []
    for idx, batch in enumerate(batches, 1):
        tmp_path = final_out_path.with_name(f"{final_out_path.stem}_upload_{idx}{final_out_path.suffix}")
        write_transactions(tmp_path, batch, FIELDNAMES)
        vlog(f"[firefly] Batch {idx}/{total}: {tmp_path.name}")
        try:
            result = upload_to_firefly(tmp_path, firefly_cfg, config_dir, vlog)
            summary = summarize_firefly_result(result)
            if summary:
                vlog(f"[firefly] Batch {idx} response:\n{summary}")
                summaries.append(f"Batch {idx}/{total}:\n{summary}")
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass

    return summaries


def clean_firefly_text(raw: str) -> str:
    if not raw:
        return ""
    working = raw.replace("\r", "")
    anchor_pattern = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE)

    def repl_anchor(match: re.Match) -> str:
        href, label = match.group(1), match.group(2)
        return f"{html.unescape(label)} ({href})"

    working = anchor_pattern.sub(repl_anchor, working)
    working = re.sub(r"<br\s*/?>", "\n", working, flags=re.IGNORECASE)
    working = re.sub(r"</?(?:p|div|span|strong|em)[^>]*>", "\n", working, flags=re.IGNORECASE)
    working = re.sub(r"<[^>]+>", "", working)
    working = html.unescape(working)
    lines = [line.strip() for line in working.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def summarize_firefly_result(result: dict | None) -> str:
    if not result:
        return ""
    if isinstance(result, dict):
        raw_text = result.get("text")
        summary = clean_firefly_text(raw_text) if isinstance(raw_text, str) else ""
        extras = {k: v for k, v in result.items() if k != "text" and v not in (None, "")}
        if extras:
            extras_json = json.dumps(extras, indent=2, default=str)
            summary = f"{summary}\n{extras_json}" if summary else extras_json
        return summary.strip()
    return clean_firefly_text(str(result))


def upload_to_firefly(csv_path: Path, firefly_cfg: dict, config_dir: Optional[Path], vlog) -> dict:
    """Upload the merged CSV to Firefly's data importer."""
    try:
        import requests
    except ImportError as exc:  # pragma: no cover - requests is optional dependency
        raise RuntimeError("Firefly upload requires the 'requests' package to be installed.") from exc

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV to upload not found: {csv_path}")

    url_raw = str(firefly_cfg.get("url") or "").strip()
    if not url_raw:
        raise ValueError("Firefly upload URL is not configured.")
    secret = str(firefly_cfg.get("secret") or "").strip()
    url = url_raw
    if secret:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}secret={secret}"
    display_url = url_raw

    token = str(firefly_cfg.get("token") or "").strip()
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    json_config = firefly_cfg.get("json_config") or ""
    json_path: Optional[Path]
    if json_config:
        candidate = Path(json_config)
        if not candidate.is_absolute() and config_dir is not None:
            candidate = (config_dir / candidate).resolve()
        else:
            candidate = candidate.resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"Firefly importer JSON not found: {candidate}")
        json_path = candidate
    else:
        json_path = None

    timeout = firefly_cfg.get("timeout")
    try:
        timeout_value = float(timeout) if timeout is not None else 30.0
    except (TypeError, ValueError):
        timeout_value = 30.0

    vlog(f"[firefly] Uploading {csv_path.name} -> {display_url}")

    with ExitStack() as stack:
        csv_file = stack.enter_context(csv_path.open("rb"))
        files = {
            "importable": (csv_path.name, csv_file, "text/csv"),
        }
        if json_path is not None:
            json_file = stack.enter_context(json_path.open("rb"))
            files["json"] = (json_path.name, json_file, "application/json")

        response = requests.post(url, headers=headers, files=files, timeout=timeout_value)

    try:
        response.raise_for_status()
    except Exception as exc:
        details = response.text.strip()
        raise RuntimeError(f"Firefly upload failed with status {response.status_code}: {details}") from exc

    try:
        return response.json()
    except Exception:
        return {"text": response.text.strip()}

def process_file(path: Path, cfg: dict, vlog) -> List[Dict[str, str]]:
    if not path.exists():
        print(f"WARNING: {path} does not exist, skipping.", file=sys.stderr)
        return []
    suffix = path.suffix.lower()
    if suffix in MT940_SUFFIXES:
        parsed = parse_bunq_mt940(path, cfg)
        for row in parsed:
            row.setdefault("source_file", path.name)
        vlog(f"[parse] bunq-mt940: {path.name} -> {len(parsed)} rows")
        return parsed

    rows, fields = csv_reader_autodetect(path)
    if not fields:
        print(f"WARNING: {path} appears empty, skipping.", file=sys.stderr)
        return []
    if is_bunq_header(fields):
        parsed = parse_bunq(rows, cfg)
        for row in parsed:
            row.setdefault("source_file", path.name)
        vlog(f"[parse] bunq: {path.name} -> {len(parsed)} rows")
        return parsed
    if is_ing_header(fields):
        parsed = parse_ing(rows, cfg)
        for row in parsed:
            row.setdefault("source_file", path.name)
        vlog(f"[parse] ING:  {path.name} -> {len(parsed)} rows")
        return parsed
    parsed_ing = parse_ing(rows, cfg)
    for row in parsed_ing:
        row.setdefault("source_file", path.name)
    parsed_bunq = parse_bunq(rows, cfg)
    for row in parsed_bunq:
        row.setdefault("source_file", path.name)
    score_ing = sum(bool(r.get("description")) for r in parsed_ing)
    score_bunq = sum(bool(r.get("description")) for r in parsed_bunq)
    parsed = parsed_ing if score_ing >= score_bunq else parsed_bunq
    bank = "ING?" if score_ing >= score_bunq else "bunq?"
    vlog(f"[parse] Heuristic as {bank}: {path.name} -> {len(parsed)} rows")
    return parsed


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Merge Bunq and ING exports for Firefly import.")
    parser.add_argument("--ing", nargs="*", default=[], help="Path(s) to ING CSV file(s)")
    parser.add_argument("--bunq", nargs="*", default=[], help="Path(s) to bunq CSV file(s)")
    parser.add_argument("-c", "--config", default=None, help="YAML config path")
    parser.add_argument(
        "-o",
        "--out",
        default=None,
        help="Final output CSV path (post-AI). If --output-dir is given, this overrides the auto-named final file.",
    )

    parser.add_argument("--input-dir", default=None, help="Directory containing CSV files to process")
    parser.add_argument("--output-dir", default=None, help="Directory to store merged outputs with timestamp names")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--progress", action="store_true", help="Show simple progress for long operations")
    parser.add_argument("--no-dedup", action="store_true", help="Disable deduplication step")
    parser.add_argument(
        "--dedupe-first-only",
        action="store_true",
        help="Treat every repeated fingerprint as duplicate and keep only first occurrence (including same-file repeats).",
    )
    parser.add_argument(
        "--echo-transactions",
        type=int,
        default=0,
        help="Print the first N merged transactions for inspection",
    )

    parser.add_argument("--ai-categorize", action="store_true", help="Use Ollama model to add category and tags")
    parser.add_argument("--ollama-url", default=None, help="Override Ollama base URL (e.g., http://localhost:11434)")
    parser.add_argument("--ollama-model", default=None, help="Override model name (e.g., gpt-oss:20b)")
    parser.add_argument("--ai-temperature", type=float, default=None, help="Sampling temperature (default from config)")
    parser.add_argument(
        "--ai-max-concurrency",
        type=int,
        default=None,
        help="Maximum concurrent AI requests (default 1, max 5)",
    )

    parser.add_argument("--push-firefly", action="store_true", help="Upload the merged CSV to Firefly after generation")
    parser.add_argument("--firefly-url", default=None, help="Firefly autoupload endpoint (e.g., https://.../autoupload)")
    parser.add_argument("--firefly-secret", default=None, help="Secret query parameter for the Firefly autoupload endpoint")
    parser.add_argument("--firefly-token", default=None, help="Firefly personal access token for Authorization header")
    parser.add_argument("--firefly-json", default=None, help="Path to Firefly importer JSON configuration file")
    parser.add_argument("--firefly-timeout", type=float, default=None, help="Timeout for Firefly upload in seconds (default 30)")

    parser.add_argument("--firefly-batch-size", type=int, default=None, help="Maximum transactions per upload batch (default 50)")

    args = parser.parse_args(argv)

    def vlog(*a, **k):
        if args.verbose:
            print(*a, **k, file=sys.stderr)

    config_dir: Optional[Path] = Path(args.config).resolve().parent if args.config else None
    cfg = load_config(args.config)
    if args.ollama_url:
        cfg["ai"]["ollama_url"] = args.ollama_url
    if args.ollama_model:
        cfg["ai"]["model"] = args.ollama_model
    if args.ai_temperature is not None:
        cfg["ai"]["temperature"] = args.ai_temperature
    if args.ai_categorize:
        cfg["ai"]["enabled"] = True
    if args.ai_max_concurrency is not None:
        cfg["ai"]["max_concurrency"] = max(1, min(5, args.ai_max_concurrency))

    firefly_cfg = cfg.setdefault("firefly", {}) or {}
    if args.firefly_url:
        firefly_cfg["url"] = args.firefly_url
    if args.firefly_secret:
        firefly_cfg["secret"] = args.firefly_secret
    if args.firefly_token:
        firefly_cfg["token"] = args.firefly_token
    if args.firefly_json:
        firefly_cfg["json_config"] = args.firefly_json
    if args.firefly_timeout is not None:
        try:
            firefly_cfg["timeout"] = max(1.0, float(args.firefly_timeout))
        except (TypeError, ValueError):
            firefly_cfg["timeout"] = 30.0
    if args.firefly_batch_size is not None:
        try:
            firefly_cfg["batch_size"] = max(1, int(args.firefly_batch_size))
        except (TypeError, ValueError):
            firefly_cfg["batch_size"] = 50
    if args.push_firefly:
        firefly_cfg["enabled"] = True

    enabled_raw = firefly_cfg.get("enabled")
    if isinstance(enabled_raw, str):
        firefly_cfg["enabled"] = enabled_raw.strip().lower() in {"1", "true", "yes", "on"}

    if args.input_dir:
        indir = Path(args.input_dir)
        vlog(f"[scan] Looking for bank statements in: {args.input_dir}")
        if indir.exists() and indir.is_dir():
            for file in sorted(indir.iterdir()):
                if not file.is_file():
                    continue
                suffix = file.suffix.lower()
                if suffix not in SUPPORTED_INPUT_SUFFIXES:
                    continue
                if suffix in MT940_SUFFIXES:
                    args.bunq.append(str(file))
                    vlog(f"[scan] bunq-mt940: {file.name}")
                    continue
                rows, fields = csv_reader_autodetect(file)
                if args.verbose:
                    print(f"[scan] {file.name} headers: {fields}", file=sys.stderr)
                # Check bunq first because ING detection includes some overlapping fields.
                if is_bunq_header(fields):
                    args.bunq.append(str(file))
                    vlog(f"[scan] bunq: {file.name} ({len(rows)} rows)")
                elif is_ing_header(fields):
                    args.ing.append(str(file))
                    vlog(f"[scan] ING:  {file.name} ({len(rows)} rows)")
                else:
                    args.ing.append(str(file))
                    vlog(f"[scan] unknown->heuristic: {file.name} ({len(rows)} rows)")
        else:
            print(f"WARNING: input-dir {indir} not found or not a directory.", file=sys.stderr)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_outdir = Path(args.output_dir) if args.output_dir else Path(".")
    if args.output_dir:
        base_outdir.mkdir(parents=True, exist_ok=True)

    explicit_out = Path(args.out) if args.out else None

    final_out_path: Optional[Path]
    duplicates_out_path: Optional[Path]

    final_out_path = explicit_out
    duplicates_out_path = final_out_path.with_name(f"{final_out_path.stem}_duplicates{final_out_path.suffix}") if final_out_path else None

    unified: List[Dict[str, str]] = []
    for path_str in args.ing:
        unified.extend(process_file(Path(path_str), cfg, vlog))
    for path_str in args.bunq:
        unified.extend(process_file(Path(path_str), cfg, vlog))

    vlog(f"[merge] Total parsed rows: {len(unified)}")

    def _sort_key(row):
        ds = row.get("date") or ""
        try:
            dt = datetime.strptime(ds, "%Y-%m-%d")
        except ValueError:
            dt = None
        return (dt or datetime.max, ds, row.get("external_id") or "", row.get("description") or "")

    unified.sort(key=_sort_key)

    savings_map = build_savings_map(cfg)
    own_tokens = {
        str(acc).replace(" ", "").upper()
        for acc in cfg.get("own_accounts", []) or []
        if isinstance(acc, str)
    }
    for info in savings_map.values():
        acct = str(info.get("account") or "").replace(" ", "").upper()
        if acct:
            own_tokens.add(acct)
    duplicates: List[Dict[str, str]] = []

    if args.no_dedup:
        deduped = list(unified)
        vlog(f"[dedup] Skipped (no-dedup). Total: {len(deduped)}")
    else:
        def _normalize_token(value: str) -> str:
            return "".join((value or "").strip().upper().split())

        def _normalize_text(value: str) -> str:
            return " ".join((value or "").strip().lower().split())

        def _normalize_description(value: str) -> str:
            text = (value or "").strip().lower()
            if not text:
                return ""
            normalized = unicodedata.normalize("NFKD", text)
            ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
            return re.sub(r"[^a-z0-9]+", "", ascii_text)

        def _amount_to_cents(value: str) -> int:
            raw = normalize_decimal(str(value or ""))
            if not raw:
                return 0
            try:
                return int(round(float(raw) * 100))
            except ValueError:
                return 0

        def _is_strict_transfer_candidate(row: Dict[str, str]) -> bool:
            date_val = (row.get("date") or "").strip()
            if not date_val:
                return False
            src = _normalize_token(row.get("source_account_number") or "")
            dst = _normalize_token(row.get("destination_account_number") or "")
            if not src or not dst or src == dst:
                return False
            if src not in own_tokens or dst not in own_tokens:
                return False
            amount_cents = _amount_to_cents(row.get("amount") or "")
            return amount_cents != 0

        def _strict_group_key(row: Dict[str, str]) -> Optional[Tuple[str, int, str, str]]:
            if not _is_strict_transfer_candidate(row):
                return None
            src = _normalize_token(row.get("source_account_number") or "")
            dst = _normalize_token(row.get("destination_account_number") or "")
            pair = "|".join(sorted([src, dst]))
            date_val = (row.get("date") or "").strip()
            amount_abs = abs(_amount_to_cents(row.get("amount") or ""))
            currency = _normalize_token(row.get("currency_code") or cfg.get("currency_code", "EUR"))
            return (date_val, amount_abs, currency, pair)

        def _description_pair_mode(desc_a: str, desc_b: str) -> str:
            if desc_a and desc_b:
                return "normalized_equal" if desc_a == desc_b else "mismatch"
            if desc_a or desc_b:
                return "one_missing"
            return "both_missing"

        def _description_pair_priority(mode: str) -> int:
            return {
                "normalized_equal": 0,
                "one_missing": 1,
                "both_missing": 2,
                "mismatch": 3,
            }.get(mode, 4)

        def _build_transfer_reasoning(
            dropped: Dict[str, object],
            kept: Dict[str, object],
            desc_mode: str,
        ) -> str:
            desc_rule = {
                "normalized_equal": "both descriptions normalized to the same value",
                "one_missing": "one description was empty (allowed in strict mode)",
                "both_missing": "both descriptions were empty",
                "mismatch": "descriptions differed after normalization (allowed as lower-priority fallback)",
            }.get(desc_mode, "description rule evaluated")
            date_val = str(dropped.get("date") or "")
            amount_abs = int(abs(int(dropped.get("amount_cents") or 0)))
            currency = str(dropped.get("currency") or "")
            drop_src = str(dropped.get("src") or "")
            drop_dst = str(dropped.get("dst") or "")
            kept_src = str(kept.get("src") or "")
            kept_dst = str(kept.get("dst") or "")
            drop_amt = int(dropped.get("amount_cents") or 0) / 100.0
            kept_amt = int(kept.get("amount_cents") or 0) / 100.0
            drop_file = str(dropped.get("source_file") or "")
            kept_file = str(kept.get("source_file") or "")
            kept_external_id = str(kept.get("external_id") or "")
            currency_label = currency or "N/A"
            sign_mode = "same sign" if (drop_amt == 0 or kept_amt == 0 or (drop_amt > 0) == (kept_amt > 0)) else "opposite sign"
            return (
                f"Strict transfer pair with kept external_id={kept_external_id or 'N/A'}; "
                f"same date={date_val}; same absolute amount={amount_abs / 100.0:.2f} {currency_label}; "
                f"mirrored own-account direction {drop_src}->{drop_dst} vs {kept_src}->{kept_dst}; "
                f"amount signs observed as {sign_mode} ({drop_amt:.2f} vs {kept_amt:.2f}); "
                f"source files observed as ({drop_file or 'N/A'} vs {kept_file or 'N/A'}); "
                f"{desc_rule}."
            )

        def _dedupe_first_only_key(row: Dict[str, str]) -> tuple:
            src = _normalize_token(row.get("source_account_number") or "")
            dst = _normalize_token(row.get("destination_account_number") or "")
            return (
                (row.get("date") or "").strip(),
                _amount_to_cents(row.get("amount") or ""),
                src,
                dst,
                _normalize_text(row.get("description") or ""),
                _normalize_token(row.get("type") or ""),
                _normalize_token(row.get("currency_code") or ""),
                _normalize_text(row.get("tags") or ""),
                _normalize_token(row.get("external_id") or ""),
            )

        dup_count = 0
        if args.dedupe_first_only:
            seen_first_only: Dict[tuple, List[Dict[str, str]]] = {}
            deduped = []
            for r in unified:
                key = _dedupe_first_only_key(r)
                bucket = seen_first_only.setdefault(key, [])
                if bucket:
                    dup_count += 1
                    duplicate_entry = dict(r)
                    duplicate_entry["duplicate_reason"] = "duplicate_first_only"
                    duplicate_entry["duplicate_reasoning"] = (
                        "Matched an earlier row on strict first-only fingerprint "
                        "(date, signed amount, source/destination accounts, normalized description, "
                        "type, currency, tags, external_id)."
                    )
                    duplicate_entry["duplicate_of_external_id"] = str(bucket[0].get("external_id") or "")
                    duplicates.append(duplicate_entry)
                    if args.verbose:
                        print(
                            f"[dedup] drop {r.get('external_id')} {r.get('date')} {r.get('amount')} {r.get('description')}",
                            file=sys.stderr,
                        )
                        print(f"  [dedup] kept  {bucket[0]}", file=sys.stderr)
                        print(f"  [dedup] drop  {r}", file=sys.stderr)
                    continue
                bucket.append(r)
                deduped.append(r)
            mode_label = "first-only"
        else:
            grouped: Dict[Tuple[str, int, str, str], List[Dict[str, object]]] = {}
            for idx, row in enumerate(unified):
                group_key = _strict_group_key(row)
                if group_key is None:
                    continue
                grouped.setdefault(group_key, []).append(
                    {
                        "idx": idx,
                        "row": row,
                        "date": (row.get("date") or "").strip(),
                        "amount_cents": _amount_to_cents(row.get("amount") or ""),
                        "currency": _normalize_token(row.get("currency_code") or cfg.get("currency_code", "EUR")),
                        "source_file": (row.get("source_file") or "").strip(),
                        "external_id": str(row.get("external_id") or ""),
                        "src": _normalize_token(row.get("source_account_number") or ""),
                        "dst": _normalize_token(row.get("destination_account_number") or ""),
                        "desc_norm": _normalize_description(row.get("description") or ""),
                    }
                )

            dropped_indices: set[int] = set()
            matched_pairs = 0
            paired_indices: set[int] = set()

            for group_key in sorted(grouped.keys()):
                entries = grouped[group_key]
                forward = sorted(
                    [
                        item
                        for item in entries
                        if str(item.get("src") or "") <= str(item.get("dst") or "")
                    ],
                    key=lambda item: (int(item.get("idx") or 0), str(item.get("external_id") or "")),
                )
                reverse = sorted(
                    [
                        item
                        for item in entries
                        if str(item.get("src") or "") > str(item.get("dst") or "")
                    ],
                    key=lambda item: (int(item.get("idx") or 0), str(item.get("external_id") or "")),
                )
                if not forward or not reverse:
                    continue

                pairings: List[Tuple[Dict[str, object], Dict[str, object], str]] = []
                used_reverse_indices: set[int] = set()

                for left_item in forward:
                    left_idx = int(left_item.get("idx") or 0)
                    if left_idx in paired_indices:
                        continue

                    best_candidate: Optional[Tuple[Tuple[int, int, int], Dict[str, object], str]] = None
                    for right_item in reverse:
                        right_idx = int(right_item.get("idx") or 0)
                        if right_idx in paired_indices or right_idx in used_reverse_indices:
                            continue
                        if str(left_item.get("src") or "") != str(right_item.get("dst") or ""):
                            continue
                        if str(left_item.get("dst") or "") != str(right_item.get("src") or ""):
                            continue
                        desc_mode = _description_pair_mode(
                            str(left_item.get("desc_norm") or ""),
                            str(right_item.get("desc_norm") or ""),
                        )
                        score = (
                            _description_pair_priority(desc_mode),
                            abs(left_idx - right_idx),
                            right_idx,
                        )
                        if best_candidate is None or score < best_candidate[0]:
                            best_candidate = (score, right_item, desc_mode)

                    if best_candidate is None:
                        continue
                    _, chosen_right, chosen_desc_mode = best_candidate
                    chosen_right_idx = int(chosen_right.get("idx") or 0)
                    used_reverse_indices.add(chosen_right_idx)
                    paired_indices.add(left_idx)
                    paired_indices.add(chosen_right_idx)
                    pairings.append((left_item, chosen_right, chosen_desc_mode))

                for left_item, right_item, desc_mode in pairings:
                    matched_pairs += 1

                    if int(left_item.get("idx") or 0) <= int(right_item.get("idx") or 0):
                        kept_item = left_item
                        dropped_item = right_item
                    else:
                        kept_item = right_item
                        dropped_item = left_item

                    drop_idx = int(dropped_item.get("idx") or 0)
                    if drop_idx in dropped_indices:
                        continue
                    dropped_indices.add(drop_idx)
                    dup_count += 1

                    duplicate_entry = dict(dropped_item.get("row") or {})
                    duplicate_entry["duplicate_reason"] = "strict_transfer_pair"
                    duplicate_entry["duplicate_reasoning"] = _build_transfer_reasoning(
                        dropped=dropped_item,
                        kept=kept_item,
                        desc_mode=desc_mode,
                    )
                    duplicate_entry["duplicate_of_external_id"] = str(kept_item.get("external_id") or "")
                    duplicates.append(duplicate_entry)

                    if args.verbose:
                        print(
                            f"[dedup] drop strict-pair {duplicate_entry.get('external_id')} "
                            f"{duplicate_entry.get('date')} {duplicate_entry.get('amount')} "
                            f"{duplicate_entry.get('description')}",
                            file=sys.stderr,
                        )
                        print(f"  [dedup] kept  {kept_item.get('row')}", file=sys.stderr)
                        print(f"  [dedup] drop  {duplicate_entry}", file=sys.stderr)

            deduped = [row for idx, row in enumerate(unified) if idx not in dropped_indices]
            mode_label = "strict-transfer-pairs"
            vlog(
                f"[dedup] strict candidate groups: {len(grouped)}; matched pairs: {matched_pairs}; "
                f"dropped rows: {dup_count}"
            )

        vlog(f"[dedup] Mode={mode_label}. Removed {dup_count} duplicates. Kept: {len(deduped)}")

    # Compute running balances per account/currency, seeding from earliest snapshot if present
    def _read_snapshot(path: Path) -> Dict[str, Dict[str, str]]:
        out: Dict[str, Dict[str, str]] = {}
        if not path.exists():
            return out
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f, delimiter=";")
                for row in reader:
                    acct = (row.get("Account") or "").strip()
                    if not acct:
                        continue
                    token = acct.replace(" ", "").upper()
                    bal_raw = row.get("Book balance") or row.get("Value balance") or ""
                    cur_raw = (row.get("Currency") or "").strip().upper() or cfg.get("currency_code", "EUR")
                    out[token] = {
                        "account": acct,
                        "currency": cur_raw,
                        "balance": bal_raw,
                        "date": (row.get("Date") or "").strip(),
                    }
        except Exception:
            pass
        return out

    balances_dir = Path("balances")
    snapshot_files = sorted(balances_dir.glob("All_current_accounts_*.csv")) if balances_dir.exists() else []
    start_snapshot = _read_snapshot(snapshot_files[0]) if snapshot_files else {}
    end_snapshot = _read_snapshot(snapshot_files[-1]) if snapshot_files else {}

    def _parse_dt(date_str: str) -> datetime | None:
        s = (date_str or "").strip()
        if not s:
            return None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
        return None

    start_dt = None
    if start_snapshot:
        # any date present will do; snapshots should be single-date dumps
        try:
            start_dt = _parse_dt(next(iter(start_snapshot.values())).get("date", ""))
        except Exception:
            start_dt = None
    end_dt = None
    if end_snapshot:
        try:
            end_dt = _parse_dt(next(iter(end_snapshot.values())).get("date", ""))
        except Exception:
            end_dt = None

    balances: Dict[tuple, float] = {}
    for token, info in start_snapshot.items():
        cur = info.get("currency") or cfg.get("currency_code", "EUR")
        key = (token, cur)
        try:
            seed = float(normalize_decimal(str(info.get("balance") or "0")))
        except Exception:
            seed = 0.0
        balances[key] = seed

    def _parse_amount(val: str | float | int | None) -> float:
        try:
            return float(normalize_decimal(str(val)))
        except Exception:
            return 0.0

    for r in deduped:
        src = (r.get("source_account_number") or "").replace(" ", "").upper()
        if not src:
            r["assumed_balance"] = ""
            continue
        dt = _parse_dt(r.get("date") or "")
        if start_dt and dt and dt <= start_dt:
            # snapshot is end-of-day; skip applying same-day/earlier transactions
            r["assumed_balance"] = ""
            continue
        if end_dt and dt and dt > end_dt:
            # beyond snapshot horizon; still emit but do not affect balances
            r["assumed_balance"] = ""
            continue
        cur = (r.get("currency_code") or cfg.get("currency_code", "EUR")).upper()
        amt = _parse_amount(r.get("amount"))
        reported = r.get("reported_balance")
        try:
            rep_val = float(normalize_decimal(str(reported)))
        except Exception:
            rep_val = None
        key = (src, cur)
        balances[key] = balances.get(key, 0.0) + amt
        if rep_val is not None:
            balances[key] = rep_val
        r["assumed_balance"] = f"{balances[key]:.2f}"

    # Write reconciliation file comparing start + delta vs end snapshot
    def _write_reconciliation(base_path: Path) -> None:
        delta_map: Dict[tuple, float] = {}
        tx_counts: Dict[tuple, int] = {}
        for r in deduped:
            src = (r.get("source_account_number") or "").replace(" ", "").upper()
            if not src:
                continue
            dt = _parse_dt(r.get("date") or "")
            if start_dt and dt and dt <= start_dt:
                continue
            if end_dt and dt and dt > end_dt:
                continue
            cur = (r.get("currency_code") or cfg.get("currency_code", "EUR")).upper()
            amt = _parse_amount(r.get("amount"))
            key = (src, cur)
            delta_map[key] = delta_map.get(key, 0.0) + amt
            tx_counts[key] = tx_counts.get(key, 0) + 1

        all_keys = set(delta_map.keys()) | {(k, (v.get("currency") or cfg.get("currency_code", "EUR"))) for k, v in start_snapshot.items()} | {(k, (v.get("currency") or cfg.get("currency_code", "EUR"))) for k, v in end_snapshot.items()}

        rows_out: List[Dict[str, str]] = []
        for token, cur in sorted(all_keys):
            start_info = start_snapshot.get(token, {})
            end_info = end_snapshot.get(token, {})
            try:
                start_bal = float(normalize_decimal(str(start_info.get("balance") or 0)))
            except Exception:
                start_bal = 0.0
            end_bal_raw = end_info.get("balance")
            try:
                end_bal = float(normalize_decimal(str(end_bal_raw)))
            except Exception:
                end_bal = None
            delta = delta_map.get((token, cur), 0.0)
            expected = start_bal + delta
            diff = "" if end_bal is None else f"{end_bal - expected:.2f}"
            rows_out.append(
                {
                    "account_number": start_info.get("account") or end_info.get("account") or token,
                    "currency_code": cur,
                    "start_balance": f"{start_bal:.2f}",
                    "delta": f"{delta:.2f}",
                    "expected_end_balance": f"{expected:.2f}",
                    "snapshot_end_balance": "" if end_bal is None else f"{end_bal:.2f}",
                    "diff": diff,
                    "transactions": str(tx_counts.get((token, cur), 0)),
                }
            )

        rec_path = final_out_path.with_name(f"{final_out_path.stem}_reconciliation{final_out_path.suffix}")
        rec_fields = [
            "account_number",
            "currency_code",
            "start_balance",
            "delta",
            "expected_end_balance",
            "snapshot_end_balance",
            "diff",
            "transactions",
        ]
        write_transactions(rec_path, rows_out, rec_fields)

    dates = [r.get("date") for r in deduped if r.get("date")]
    if dates:
        min_date = min(dates)
        max_date = max(dates)
    else:
        current = datetime.now().strftime("%Y-%m-%d")
        min_date = max_date = current
    date_slug = f"{min_date}_to_{max_date}"

    if final_out_path is None:
        base_name = f"merged_{date_slug}_{timestamp}.csv"
        final_out_path = (base_outdir / base_name).resolve()
        final_out_path.parent.mkdir(parents=True, exist_ok=True)
        duplicates_out_path = final_out_path.with_name(f"{final_out_path.stem}_duplicates{final_out_path.suffix}")
        archive_previous_exports(final_out_path.parent, final_out_path, vlog)
    else:
        final_out_path = final_out_path.resolve()
        final_out_path.parent.mkdir(parents=True, exist_ok=True)
        if duplicates_out_path is None:
            duplicates_out_path = final_out_path.with_name(f"{final_out_path.stem}_duplicates{final_out_path.suffix}")
        archive_previous_exports(final_out_path.parent, final_out_path, vlog)

    if duplicates_out_path is None:
        duplicates_out_path = final_out_path.with_name(f"{final_out_path.stem}_duplicates{final_out_path.suffix}")
    duplicates_out_path = duplicates_out_path.resolve()

    vlog(f"[paths] FINAL: {final_out_path}")
    vlog(f"[paths] DUPES: {duplicates_out_path}")

    if args.echo_transactions and args.echo_transactions > 0:
        print(
            f"[echo] Showing first {min(args.echo_transactions, len(deduped))} transactions:",
            file=sys.stderr,
        )
        for i, r in enumerate(deduped[: args.echo_transactions], 1):
            print(
                f" {i:04d} {r.get('date')} {r.get('amount'):>10} {r.get('type'):>10} | {r.get('description')[:80]}",
                file=sys.stderr,
            )

    def flush_final(_: Dict[str, str] | None = None) -> None:
        write_transactions(final_out_path, deduped)

    flush_final()
    _write_reconciliation(final_out_path)

    if duplicates:
        write_transactions(duplicates_out_path, duplicates, DUPLICATE_FIELDNAMES)
        print(f"[dedup] DUPLICATES saved: {duplicates_out_path} ({len(duplicates)} rows)", file=sys.stderr)
    else:
        try:
            if duplicates_out_path.exists():
                duplicates_out_path.unlink()
        except OSError:
            pass

    print(f"[write] FINAL saved: {final_out_path} ({len(deduped)} rows)", file=sys.stderr)

    push_firefly = bool(firefly_cfg.get("enabled"))
    if push_firefly:
        try:
            summaries = upload_batches(final_out_path, deduped, firefly_cfg, config_dir, vlog)
        except Exception as exc:
            print(f"[firefly] Upload failed: {exc}", file=sys.stderr)
        else:
            if summaries:
                cleaned = '\n\n'.join(summaries)
                print(f"[firefly] Upload succeeded:\n{cleaned}", file=sys.stderr)
            else:
                print("[firefly] Upload succeeded.", file=sys.stderr)

    print("[summary] Done.", file=sys.stderr)


__all__ = ["main"]

