"""Utility helpers for Firefly merge."""

from __future__ import annotations

import csv
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple, Dict


def normalize_decimal(value: str) -> str:
    if value is None:
        return ""
    v = value.strip().replace('\u00A0', ' ').replace(' ', '')
    if ',' in v and '.' in v:
        v = v.replace('.', '').replace(',', '.')
    elif ',' in v:
        v = v.replace(',', '.')
    return v


def parse_date(date_str: str) -> str:
    s = (date_str or "").strip()
    fmts = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%d-%m-%y",
        "%d/%m/%y",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M",
        "%Y%m%d",
        "%Y%m%d%H%M%S",
        "%Y%m%d %H:%M:%S",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s or ""


def stable_hash(parts: Iterable[str]) -> str:
    clean = "|".join((p or "").strip() for p in parts)
    return hashlib.sha1(clean.encode("utf-8")).hexdigest()[:16]


def csv_reader_autodetect(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        except Exception:
            dialect = csv.excel
            dialect.delimiter = ';'
        reader = csv.DictReader(f, dialect=dialect)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    return rows, fieldnames


__all__ = [
    "normalize_decimal",
    "parse_date",
    "stable_hash",
    "csv_reader_autodetect",
]
