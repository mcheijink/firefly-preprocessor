"""Savings-account helper utilities."""

from __future__ import annotations

from typing import Dict, Optional, Set
import re

SAVINGS_ID_PATTERN = re.compile(r'^[A-Za-z]\d+$')


def gather_savings_ids(cfg: dict) -> Set[str]:
    ids: Set[str] = set()
    for entry in cfg.get("own_accounts", []) or []:
        if isinstance(entry, str):
            token = entry.strip()
            if token and SAVINGS_ID_PATTERN.fullmatch(token):
                ids.add(token.upper())
    raw = cfg.get("savings_accounts") or {}
    if isinstance(raw, dict):
        for key in raw.keys():
            if isinstance(key, str):
                token = key.strip()
                if token:
                    ids.add(token.upper())
    alias_map = cfg.get("account_aliases", {}) or {}
    for key in alias_map.keys():
        if isinstance(key, str):
            token = key.strip()
            if token and SAVINGS_ID_PATTERN.fullmatch(token):
                ids.add(token.upper())
    return ids


def build_savings_map(cfg: dict) -> Dict[str, Dict[str, str]]:
    alias_map = cfg.get("account_aliases", {}) or {}
    savings_map: Dict[str, Dict[str, str]] = {}
    raw = cfg.get("savings_accounts") or {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if not isinstance(key, str):
                continue
            sid = key.strip().upper()
            if not sid:
                continue
            account_val = sid
            name_val = ""
            if isinstance(value, dict):
                account_val = str(value.get("account") or value.get("iban") or sid).strip() or sid
                name_val = str(value.get("name") or "").strip()
            elif isinstance(value, str):
                account_val = value.strip() or sid
            savings_map[sid] = {
                "account": account_val,
                "name": name_val or str(alias_map.get(account_val) or alias_map.get(sid) or sid).strip(),
            }
    for sid in gather_savings_ids(cfg):
        if sid not in savings_map:
            savings_map[sid] = {
                "account": sid,
                "name": str(alias_map.get(sid) or "").strip(),
            }
    return savings_map


def resolve_account_name(account: str, alias_map: Dict[str, str], fallback: str = "") -> str:
    acct = (account or "").strip()
    if acct:
        alias = alias_map.get(acct)
        if alias:
            return str(alias).strip()
    fallback = (fallback or "").strip()
    if fallback:
        return fallback
    return acct


__all__ = [
    "SAVINGS_ID_PATTERN",
    "gather_savings_ids",
    "build_savings_map",
    "resolve_account_name",
]
