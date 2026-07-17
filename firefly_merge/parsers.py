"""Bank-specific parsing logic."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import re

from .savings import build_savings_map, gather_savings_ids, resolve_account_name
from .utils import normalize_decimal, parse_date, stable_hash


def _account_currency(account: str, default: str = "EUR") -> str:
    """Return GBP only for the dedicated GBP account export; otherwise default to EUR."""
    acct = (account or "").replace(" ", "").upper()
    if acct.startswith("GB48TCCL04140462886650"):
        return "GBP"
    return default or "EUR"


def is_ing_header(fields: List[str]) -> bool:
    normalized = [x.strip().lower() for x in (fields or [])]
    # Keep ING detection strict to avoid matching bunq exports on generic headers
    # like Date/Account/Counterparty/Amount.
    strong_markers = {
        "datum",
        "naam / omschrijving",
        "rekening",
        "tegenrekening",
        "code",
        "af",
        "bij",
        "bedrag (eur)",
        "mutatiesoort",
        "mededelingen",
        "name / description",
        "debit/credit",
        "notifications",
        "transaction type",
    }
    matches = sum(1 for marker in strong_markers if marker in normalized)
    return matches >= 2


def is_bunq_header(fields: List[str]) -> bool:
    normalized = [x.strip().lower() for x in (fields or [])]
    markers = {
        "interest date",
        "account",
        "counterparty",
        "name",
        "type",
        "amount",
        "description",
        "balance after",
    }
    return sum(1 for m in markers if m in normalized) >= 3


def _prepare_own_accounts(cfg: dict, savings_map: Dict[str, Dict[str, str]]) -> Set[str]:
    own_accounts_clean: Set[str] = set()
    for entry in cfg.get("own_accounts", []) or []:
        if isinstance(entry, str):
            token = entry.replace(" ", "").upper()
            if token:
                own_accounts_clean.add(token)
    for info in savings_map.values():
        acct_token = str(info.get("account") or "").replace(" ", "").upper()
        if acct_token:
            own_accounts_clean.add(acct_token)
    return own_accounts_clean


SAVINGS_IBAN_RE = re.compile(r"[A-Z]{2}\d{2}[A-Z0-9]{6,}")
MT940_TAG_RE = re.compile(r"^:(\d{2}[A-Z]?):(.*)$")
MT940_IBAN_RE = re.compile(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}")
ING_VALUE_DATE_RE = re.compile(r"(?i)\bValue date:\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
ING_CODE_RE = re.compile(r"(?i)\bCode:\s*[A-Z0-9]+\b")


def _extract_savings_account(text: str, savings_map: Dict[str, Dict[str, str]], savings_ids: Set[str]) -> str | None:
    if not text:
        return None

    upper_text = text.upper()
    compact_text = upper_text.replace(" ", "")

    tokens: Dict[str, str] = {}
    for sid, info in savings_map.items():
        account_val = str(info.get("account") or sid).strip()
        name_val = str(info.get("name") or "").strip()
        for token in [sid, account_val, name_val]:
            if not token:
                continue
            compact = token.replace(" ", "").upper()
            if not compact:
                continue
            if token is name_val and len(compact) < 6:
                continue
            tokens.setdefault(compact, account_val or sid)
    for sid in savings_ids:
        compact = sid.replace(" ", "").upper()
        if compact and compact not in tokens:
            mapped = str(savings_map.get(sid, {}).get("account") or sid)
            tokens[compact] = mapped

    for match in SAVINGS_IBAN_RE.findall(upper_text):
        key = match.replace(" ", "").upper()
        if key in tokens:
            return tokens[key]

    for compact, mapped in tokens.items():
        if compact and (compact in compact_text or compact in upper_text):
            return mapped

    return None


def _parse_mt940_fields(text: str) -> List[Tuple[str, str]]:
    fields: List[Tuple[str, str]] = []
    current_tag = ""
    current_value: List[str] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip("\ufeff\r")
        if not line:
            continue
        match = MT940_TAG_RE.match(line)
        if match:
            if current_tag:
                fields.append((current_tag, "\n".join(current_value).strip()))
            current_tag = match.group(1)
            current_value = [match.group(2)]
            continue
        if current_tag:
            current_value.append(line.strip())
    if current_tag:
        fields.append((current_tag, "\n".join(current_value).strip()))
    return fields


def _parse_mt940_value_date(raw: str) -> str:
    token = (raw or "").strip()
    if len(token) != 6 or not token.isdigit():
        return parse_date(token)
    yy = int(token[0:2])
    year = 2000 + yy if yy < 70 else 1900 + yy
    month = int(token[2:4])
    day = int(token[4:6])
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return parse_date(token)


def _clean_mt940_description(raw: str) -> str:
    text = (raw or "").replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\?\d{2}", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_mt940_61(raw: str) -> Dict[str, str]:
    line = (raw or "").replace("\r", "").replace("\n", "").strip()
    pattern = re.compile(
        r"^(?P<value_date>\d{6})(?P<entry_date>\d{4})?(?P<dc>R?[DC])(?P<fund>[A-Z])?(?P<amount>\d+(?:,\d+)?)(?P<rest>.*)$"
    )
    match = pattern.match(line)
    if not match:
        return {
            "date": parse_date(line[:10]),
            "amount": "0",
            "raw": line,
            "tx_code": "",
            "customer_ref": "",
            "bank_ref": "",
        }

    dc_mark = (match.group("dc") or "").upper()
    amount_abs = float(normalize_decimal(match.group("amount") or "0") or "0")
    is_credit = dc_mark.endswith("C")
    is_reversal = dc_mark.startswith("R")
    signed_amount = amount_abs if is_credit else -amount_abs
    if is_reversal:
        signed_amount = -signed_amount

    rest = (match.group("rest") or "").strip()
    tx_code = ""
    if rest.startswith("N") and len(rest) >= 4:
        tx_code = rest[1:4]
        rest = rest[4:]

    customer_ref = ""
    bank_ref = ""
    if "//" in rest:
        left, right = rest.split("//", 1)
        customer_ref = left.strip()
        bank_ref = right.strip()
    else:
        customer_ref = rest.strip()

    return {
        "date": _parse_mt940_value_date(match.group("value_date") or ""),
        "amount": f"{signed_amount:.2f}",
        "raw": line,
        "tx_code": tx_code,
        "customer_ref": customer_ref,
        "bank_ref": bank_ref,
    }


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).strip()


def _cleanup_ing_description_and_notes(name_desc: str, fallback_description: str, memo: str) -> Tuple[str, str]:
    base_desc = _normalize_spaces(name_desc or fallback_description or "")
    memo_text = _normalize_spaces(memo)
    if memo_text.lower().startswith("mededelingen:"):
        memo_text = _normalize_spaces(memo_text.split(":", 1)[1])

    desc_from_memo = ""
    if memo_text:
        match = re.search(
            r"(?i)\bDescription:\s*(.+?)(?=\s+\b(?:IBAN|Reference|Mandate ID|Creditor ID|Value date|Code)\b\s*:|$)",
            memo_text,
        )
        if match:
            desc_from_memo = _normalize_spaces(match.group(1))
        elif re.search(r"(?i)\bApple\s+Pay\b", memo_text):
            desc_from_memo = "Apple Pay"

    cleaned_notes = memo_text
    if cleaned_notes:
        cleaned_notes = re.sub(
            r"(?i)\bName:\s*.+?(?=\s+\b(?:Description|IBAN|Reference|Mandate ID|Creditor ID|Value date|Code)\b\s*:|$)",
            "",
            cleaned_notes,
        )
        cleaned_notes = re.sub(
            r"(?i)\bDescription:\s*.+?(?=\s+\b(?:IBAN|Reference|Mandate ID|Creditor ID|Value date|Code)\b\s*:|$)",
            "",
            cleaned_notes,
        )
        cleaned_notes = re.sub(
            r"(?i)\bIBAN:\s*.+?(?=\s+\b(?:Reference|Mandate ID|Creditor ID|Value date|Code)\b\s*:|$)",
            "",
            cleaned_notes,
        )
        cleaned_notes = ING_VALUE_DATE_RE.sub("", cleaned_notes)
        cleaned_notes = ING_CODE_RE.sub("", cleaned_notes)
        cleaned_notes = _normalize_spaces(cleaned_notes).strip("| ").strip()

    desc = desc_from_memo or base_desc
    if not desc and cleaned_notes:
        desc = cleaned_notes
    if not desc:
        desc = "ING transaction"

    if cleaned_notes and cleaned_notes == desc:
        cleaned_notes = ""

    return desc, cleaned_notes


def parse_ing(rows: List[Dict[str, str]], cfg: dict) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    alias_map = cfg.get("account_aliases", {}) or {}
    savings_map = build_savings_map(cfg)
    savings_ids = gather_savings_ids(cfg)
    own_accounts_clean = _prepare_own_accounts(cfg, savings_map)
    own_tokens = {acct.replace(" ", "").upper() for acct in own_accounts_clean}

    for r in rows:
        date = r.get("Datum") or r.get("Date") or r.get("date") or r.get("Boekingsdatum") or ""
        description = (
            r.get("Naam / Omschrijving")
            or r.get("Name / Description")
            or r.get("Omschrijving")
            or r.get("Description")
            or r.get("description")
            or ""
        )
        account = r.get("Rekening") or r.get("Account") or r.get("IBAN/BBAN") or r.get("account") or ""
        counter = r.get("Tegenrekening") or r.get("Counterparty") or r.get("Tegenpartij IBAN") or r.get("counterparty") or ""
        code = r.get("Code") or r.get("code") or ""
        af = r.get("Af") or r.get("Debit") or ""
        bij = r.get("Bij") or r.get("Credit") or ""
        debit_credit = r.get("Debit/credit") or r.get("Debit/Credit") or r.get("D/C") or ""
        amount_raw = r.get("Bedrag (EUR)") or r.get("Amount (EUR)") or r.get("Bedrag") or r.get("Amount") or ""
        mut_type = r.get("Mutatiesoort") or r.get("TransactieType") or r.get("Transaction type") or ""
        memo = r.get("Mededelingen") or r.get("Omschrijving-2") or r.get("Notifications") or ""

        af_val = (str(af).strip() or "").upper()
        bij_val = (str(bij).strip() or "").upper()
        debit_credit_val = (str(debit_credit).strip() or "").upper()

        amount_value = float(normalize_decimal(amount_raw) or "0")
        if amount_value < 0:
            amount_signed = amount_value
        else:
            amount_abs = abs(amount_value)
            if debit_credit_val in {"DEBIT", "D"}:
                amount_signed = -amount_abs
            elif debit_credit_val in {"CREDIT", "CR", "C"}:
                amount_signed = amount_abs
            elif af_val in {"AF", "DEBIT", "D"}:
                amount_signed = -amount_abs
            elif bij_val in {"BIJ", "CREDIT", "CR", "C"}:
                amount_signed = amount_abs
            else:
                amount_signed = amount_value

        account_clean = (account or "").strip()
        counter_clean = (counter or "").strip()

        this_acct_token = account_clean.replace(" ", "").upper()
        counter_acct_token = counter_clean.replace(" ", "").upper()
        if this_acct_token and counter_acct_token and this_acct_token in own_accounts_clean and counter_acct_token in own_accounts_clean:
            ttype = "transfer"
        else:
            ttype = "withdrawal" if amount_signed < 0 else "deposit"

        name_desc = (r.get("Naam / Omschrijving") or r.get("Name / Description") or "").strip()
        desc, cleaned_notes = _cleanup_ing_description_and_notes(name_desc, description.strip(), memo)

        tags_list: List[str] = []
        if mut_type:
            mut = str(mut_type).strip()
            if mut:
                tags_list.append(mut)
        tags = ",".join(dict.fromkeys(t.strip() for t in tags_list if t and t.strip()))

        notes_parts: List[str] = []
        if cleaned_notes:
            notes_parts.append(cleaned_notes)

        source_account_val = account_clean
        destination_account_val = counter_clean
        source_fallback = alias_map.get(account_clean, account_clean) or account_clean
        destination_fallback = alias_map.get(counter_clean, "") or name_desc or counter_clean or "External"

        source_number = source_account_val
        destination_number = destination_account_val

        detection_parts = [
            memo,
            cleaned_notes,
            desc,
            description,
            name_desc,
            counter,
            account_clean,
            counter_clean,
            alias_map.get(account_clean, ""),
            alias_map.get(counter_clean, ""),
            source_account_val,
            destination_account_val,
        ]
        detection_text = " ".join(part for part in detection_parts if part)
        detected_savings = _extract_savings_account(detection_text, savings_map, savings_ids)
        if detected_savings:
            savings_account_val = detected_savings
            savings_info = next((info for info in savings_map.values() if str(info.get("account") or "").replace(" ", "").upper() == savings_account_val.replace(" ", "").upper()), None)
            savings_name = ""
            if savings_info:
                savings_name = str(savings_info.get("name") or "").strip()
            if not savings_name:
                savings_name = resolve_account_name(savings_account_val, alias_map, savings_account_val)

            ttype = "transfer"
            destination_account_val = savings_account_val
            destination_fallback = savings_name or savings_account_val
            destination_number = destination_account_val
            notes_parts.append(f"Savings account: {savings_account_val}")

        notes = " | ".join(part for part in notes_parts if part)
        source_name = resolve_account_name(source_account_val, alias_map, source_fallback)
        destination_name = resolve_account_name(destination_account_val, alias_map, destination_fallback)

        source_display = source_name or source_number
        destination_display = destination_name or destination_number

        native_external_id = (r.get("Transactie ID") or r.get("Transactie referentie") or "").strip()
        external_id = native_external_id or stable_hash([
            "ING",
            date,
            account,
            counter,
            str(amount_signed),
            description,
            memo,
        ])

        out.append(
            {
                "date": parse_date(date),
                "amount": f"{amount_signed:.2f}",
                "description": desc,
                "source_account": source_display,
                "source_account_number": source_number,
                "destination_account": destination_display,
                "destination_account_number": destination_number,
                "type": ttype,
                "external_id": str(external_id),
                "currency_code": _account_currency(account_clean, cfg.get("currency_code", "EUR")),
                "notes": notes,
                "category": "",
                "tags": tags,
                "_source_bank": "ing_csv",
                "_external_id_native": "1" if native_external_id else "0",
                "internal_pair_hash": stable_hash(
                    [
                        "PAIR",
                        parse_date(date),
                        f"{abs(amount_signed):.2f}",
                        "|".join(sorted([this_acct_token, counter_acct_token])),
                    ]
                )
                if this_acct_token in own_tokens and counter_acct_token in own_tokens
                else "",
            }
        )
    return out


def parse_bunq(rows: List[Dict[str, str]], cfg: dict) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    alias_map = cfg.get("account_aliases", {}) or {}
    savings_map = build_savings_map(cfg)
    savings_ids = gather_savings_ids(cfg)
    own_accounts_clean = _prepare_own_accounts(cfg, savings_map)
    own_tokens = {acct.replace(" ", "").upper() for acct in own_accounts_clean}

    for r in rows:
        date = r.get("Date") or r.get("date") or r.get("DateUpdated") or r.get("Time") or ""
        time = r.get("Time") or r.get("time") or ""
        account = r.get("Account") or r.get("IBAN") or r.get("Monetary Account IBAN") or ""
        counter = r.get("Counterparty") or r.get("Counterparty IBAN") or r.get("Opposing IBAN") or ""
        name = r.get("Name") or r.get("counterparty name") or ""
        btype = r.get("Type") or r.get("TypeDescription") or ""
        subtype = r.get("SubType") or r.get("Subtype") or ""
        amount_raw = r.get("Amount") or r.get("amount") or r.get("Value") or ""
        description = r.get("Description") or r.get("description") or ""
        balance_after = r.get("Balance after mutation") or r.get("Balance After") or ""

        amount = float(normalize_decimal(str(amount_raw) or "0"))

        account_clean = (account or "").strip()
        counter_clean = (counter or "").strip()

        this_acct_token = account_clean.replace(" ", "").upper()
        counter_acct_token = counter_clean.replace(" ", "").upper()
        if this_acct_token and counter_acct_token and this_acct_token in own_accounts_clean and counter_acct_token in own_accounts_clean:
            ttype = "transfer"
        else:
            ttype = "withdrawal" if amount < 0 else "deposit"

        counterparty_name = (name or "").strip()

        source_account_val = account_clean
        destination_account_val = counter_clean
        source_fallback = alias_map.get(account_clean, account_clean) or account_clean
        destination_fallback = alias_map.get(counter_clean, "") or counterparty_name or counter_clean or "External"

        source_number = source_account_val
        destination_number = destination_account_val

        tags_list: List[str] = []
        if btype:
            tags_list.append(str(btype).strip())
        if subtype:
            tags_list.append(str(subtype).strip())
        tags = ",".join(dict.fromkeys(t.strip() for t in tags_list if t and t.strip()))

        desc = (description or name or "").strip()
        if not desc:
            desc = counterparty_name or subtype or btype or "bunq transaction"

        notes_parts: List[str] = []
        if counterparty_name and counterparty_name not in desc:
            notes_parts.append(f"Name: {counterparty_name}")
        if balance_after:
            notes_parts.append(f"Balance after: {balance_after}")

        detection_parts = [
            desc,
            description,
            name,
            counterparty_name,
            counter,
            account_clean,
            counter_clean,
            alias_map.get(account_clean, ""),
            alias_map.get(counter_clean, ""),
            source_account_val,
            destination_account_val,
        ]
        detection_text = " ".join(part for part in detection_parts if part)
        detected_savings = _extract_savings_account(detection_text, savings_map, savings_ids)

        if detected_savings:
            savings_account_val = detected_savings
            savings_info = next((info for info in savings_map.values() if str(info.get("account") or "").replace(" ", "").upper() == savings_account_val.replace(" ", "").upper()), None)
            savings_name = ""
            if savings_info:
                savings_name = str(savings_info.get("name") or "").strip()
            if not savings_name:
                savings_name = resolve_account_name(savings_account_val, alias_map, savings_account_val)
            ttype = "transfer"
            if amount < 0:
                destination_account_val = savings_account_val
                destination_fallback = savings_name or savings_account_val
                destination_number = destination_account_val
            else:
                source_account_val = savings_account_val
                source_fallback = savings_name or savings_account_val
                source_number = savings_account_val
                if not destination_account_val:
                    destination_account_val = account_clean or savings_account_val
                    destination_fallback = alias_map.get(account_clean, "") or counterparty_name or account_clean or "External"
                    destination_number = destination_account_val
            notes_parts.append(f"Savings account: {savings_account_val}")

        notes = " | ".join(part for part in notes_parts if part)
        source_name = resolve_account_name(source_account_val, alias_map, source_fallback)
        destination_name = resolve_account_name(destination_account_val, alias_map, destination_fallback)

        source_display = source_name or source_number
        destination_display = destination_name or destination_number

        native_external_id = (r.get("Payment ID") or r.get("ID") or "").strip()
        external_id = native_external_id or stable_hash([
            "BUNQ",
            date,
            time,
            account,
            counter,
            name,
            str(amount),
            description,
        ])

        date_str = f"{date} {time}".strip() if time else f"{date}".strip()
        out.append(
            {
                "date": parse_date(date_str),
                "amount": f"{amount:.2f}",
                "description": desc,
                "source_account": source_display,
                "source_account_number": source_number,
                "destination_account": destination_display,
                "destination_account_number": destination_number,
                "type": ttype,
                "external_id": str(external_id),
                "currency_code": _account_currency(account_clean, cfg.get("currency_code", "EUR")),
                "notes": notes,
                "category": "",
                "tags": tags,
                "_source_bank": "bunq_csv",
                "_external_id_native": "1" if native_external_id else "0",
                "internal_pair_hash": stable_hash(
                    [
                        "PAIR",
                        parse_date(date_str),
                        f"{abs(amount):.2f}",
                        "|".join(sorted([this_acct_token, counter_acct_token])),
                    ]
                )
                if this_acct_token in own_tokens and counter_acct_token in own_tokens
                else "",
            }
        )
    return out


def parse_bunq_mt940(path: Path, cfg: dict) -> List[Dict[str, str]]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")

    alias_map = cfg.get("account_aliases", {}) or {}
    savings_map = build_savings_map(cfg)
    savings_ids = gather_savings_ids(cfg)
    own_accounts_clean = _prepare_own_accounts(cfg, savings_map)
    own_tokens = {acct.replace(" ", "").upper() for acct in own_accounts_clean}

    fields = _parse_mt940_fields(text)
    account = ""
    statement_ref = ""
    out: List[Dict[str, str]] = []
    current: Optional[Dict[str, str]] = None
    statement_index = 0

    for tag, value in fields:
        if tag == "20":
            statement_ref = (value or "").strip()
            continue
        if tag == "25":
            account = (value or "").splitlines()[0].strip()
            continue
        if tag == "61":
            if current is not None:
                out.append(current)
            parsed = _parse_mt940_61(value)
            statement_index += 1

            amount = float(normalize_decimal(parsed.get("amount") or "0") or "0")
            account_clean = account.strip()
            this_acct_token = account_clean.replace(" ", "").upper()
            if amount < 0:
                source_account_val = account_clean
                destination_account_val = ""
                ttype = "withdrawal"
            else:
                source_account_val = ""
                destination_account_val = account_clean
                ttype = "deposit"

            source_number = source_account_val
            destination_number = destination_account_val
            source_fallback = alias_map.get(source_account_val, source_account_val) or source_account_val
            destination_fallback = alias_map.get(destination_account_val, destination_account_val) or destination_account_val

            tx_code = (parsed.get("tx_code") or "").strip()
            customer_ref = (parsed.get("customer_ref") or "").strip()
            bank_ref = (parsed.get("bank_ref") or "").strip()
            native_external_id = bank_ref or customer_ref
            external_id = native_external_id or stable_hash(
                [
                    "BUNQ_MT940",
                    statement_ref,
                    str(statement_index),
                    parsed.get("date") or "",
                    f"{amount:.2f}",
                    account_clean,
                    tx_code,
                ]
            )

            notes_parts: List[str] = []
            if statement_ref:
                notes_parts.append(f"Statement ref: {statement_ref}")
            if customer_ref:
                notes_parts.append(f"Customer ref: {customer_ref}")
            if bank_ref:
                notes_parts.append(f"Bank ref: {bank_ref}")

            current = {
                "date": parsed.get("date") or "",
                "amount": f"{amount:.2f}",
                "description": f"MT940 {tx_code}".strip(),
                "source_account": resolve_account_name(source_account_val, alias_map, source_fallback),
                "source_account_number": source_number,
                "destination_account": resolve_account_name(destination_account_val, alias_map, destination_fallback),
                "destination_account_number": destination_number,
                "type": ttype,
                "external_id": external_id,
                "currency_code": _account_currency(account_clean, cfg.get("currency_code", "EUR")),
                "notes": " | ".join(p for p in notes_parts if p),
                "category": "",
                "tags": ",".join(x for x in ["MT940", tx_code] if x),
                "_source_bank": "bunq_mt940",
                "_external_id_native": "1" if native_external_id else "0",
                "internal_pair_hash": "",
                "_tx_code": tx_code,
                "_customer_ref": customer_ref,
                "_bank_ref": bank_ref,
                "_statement_ref": statement_ref,
                "_statement_index": str(statement_index),
                "_this_acct_token": this_acct_token,
            }
            continue

        if tag != "86" or current is None:
            continue

        details = _clean_mt940_description(value)
        if details:
            existing_desc = (current.get("description") or "").strip()
            if not existing_desc or existing_desc.startswith("MT940 "):
                current["description"] = details
            notes = (current.get("notes") or "").strip()
            current["notes"] = f"{notes} | Details: {details}".strip(" |")

        details_compact = details.replace(" ", "").upper()
        iban_match = MT940_IBAN_RE.search(details_compact)
        counterparty = iban_match.group(0) if iban_match else ""
        amount = float(normalize_decimal(current.get("amount") or "0") or "0")
        account_clean = account.strip()
        source_number = (current.get("source_account_number") or "").strip()
        destination_number = (current.get("destination_account_number") or "").strip()
        this_acct_token = (current.get("_this_acct_token") or "").strip()
        counter_token = counterparty.replace(" ", "").upper()

        if counterparty:
            if amount < 0:
                destination_number = counterparty
            else:
                source_number = counterparty

        if this_acct_token and counter_token and this_acct_token in own_tokens and counter_token in own_tokens:
            current["type"] = "transfer"
            current["internal_pair_hash"] = stable_hash(
                [
                    "PAIR",
                    current.get("date") or "",
                    f"{abs(amount):.2f}",
                    "|".join(sorted([this_acct_token, counter_token])),
                ]
            )

        if not source_number and amount >= 0:
            source_number = counterparty
        if not destination_number and amount < 0:
            destination_number = counterparty

        source_fallback = alias_map.get(source_number, "") or source_number or "External"
        destination_fallback = alias_map.get(destination_number, "") or destination_number or "External"
        current["source_account_number"] = source_number
        current["destination_account_number"] = destination_number
        current["source_account"] = resolve_account_name(source_number, alias_map, source_fallback)
        current["destination_account"] = resolve_account_name(destination_number, alias_map, destination_fallback)

        detected_savings = _extract_savings_account(details, savings_map, savings_ids)
        if detected_savings:
            current["type"] = "transfer"
            savings_name = resolve_account_name(detected_savings, alias_map, detected_savings)
            if amount < 0:
                current["destination_account_number"] = detected_savings
                current["destination_account"] = savings_name
            else:
                current["source_account_number"] = detected_savings
                current["source_account"] = savings_name

    if current is not None:
        out.append(current)

    for row in out:
        row.pop("_this_acct_token", None)
    return out


__all__ = [
    "is_ing_header",
    "is_bunq_header",
    "parse_ing",
    "parse_bunq",
    "parse_bunq_mt940",
]


