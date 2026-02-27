"""Default and LLM-assisted transaction categorization helpers."""

from __future__ import annotations

import json
from typing import Dict, List

import requests


DEFAULT_CATEGORY_RULES = [
    ("Groceries", ["albert heijn", "jumbo", "lidl", "supermarkt", "grocery"]),
    ("Dining", ["uber eats", "thuisbezorgd", "restaurant", "mcdonald", "kfc", "starbucks"]),
    ("Transport", ["ns", "ov-chipkaart", "shell", "bp ", "q8", "parking", "uber", "bolt"]),
    ("Utilities", ["energy", "stedin", "eneco", "vattenfall", "water", "internet", "kpn", "ziggo"]),
    ("Rent", ["rent", "huur", "landlord"]),
    ("Insurance", ["verzekering", "insurance", "a.s.r", "reaal", "cz", "vgz"]),
    ("Salary", ["salary", "salaris", "payroll", "loon"]),
    ("Subscriptions", ["spotify", "netflix", "disney", "icloud", "google one", "adobe"]),
    ("Health", ["pharmacy", "apotheek", "hospital", "dentist", "tandarts"]),
    ("Shopping", ["amazon", "bol.com", "ikea", "mediamarkt", "coolblue"]),
    ("Travel", ["booking.com", "airbnb", "klm", "ryanair", "hotel"]),
    ("Taxes", ["belastingdienst", "tax"]),
    ("Transfers (internal)", ["transfer", "savings account", "spaarrekening"]),
]

DEFAULT_OLLAMA_PROMPT_TEMPLATE = """You categorize financial transactions.
Choose exactly one category from this list:
{categories_csv}
Return only compact JSON with this schema: {{"category":"<one category from list>"}}
Transaction:
{transaction_json}
"""

DEFAULT_OLLAMA_BATCH_PROMPT_TEMPLATE = """You categorize financial transactions.
Choose exactly one category from this list:
{categories_csv}
Return only compact JSON with this schema:
{{"items":[{{"row_id":"<row id from input>","category":"<one category from list>"}}]}}
Transactions:
{transactions_json}
"""


def categorize_default(row: Dict[str, str]) -> str:
    content = " ".join(
        [
            (row.get("description") or ""),
            (row.get("notes") or ""),
            (row.get("tags") or ""),
            (row.get("source_account") or ""),
            (row.get("destination_account") or ""),
        ]
    ).lower()

    txn_type = (row.get("type") or "").strip().lower()
    if txn_type == "transfer":
        return "Transfers (internal)"

    for category, keywords in DEFAULT_CATEGORY_RULES:
        if any(kw in content for kw in keywords):
            return category
    return "Other"


def categorize_ollama(
    row: Dict[str, str],
    ollama_url: str,
    model: str,
    categories: List[str],
    prompt_template: str = DEFAULT_OLLAMA_PROMPT_TEMPLATE,
    temperature: float = 0.0,
    timeout: float = 60.0,
) -> str:
    trace = categorize_ollama_with_trace(
        row=row,
        ollama_url=ollama_url,
        model=model,
        categories=categories,
        prompt_template=prompt_template,
        temperature=temperature,
        timeout=timeout,
    )
    return trace.get("category", "Other")


def categorize_ollama_with_trace(
    row: Dict[str, str],
    ollama_url: str,
    model: str,
    categories: List[str],
    prompt_template: str = DEFAULT_OLLAMA_PROMPT_TEMPLATE,
    temperature: float = 0.0,
    timeout: float = 60.0,
) -> Dict[str, str]:
    prompt = build_ollama_prompt(row, categories, prompt_template=prompt_template)
    text = request_ollama_response(
        prompt=prompt,
        ollama_url=ollama_url,
        model=model,
        temperature=temperature,
        timeout=timeout,
    )
    category = _parse_ollama_response(text, categories)
    return {"category": category, "prompt": prompt, "response": text}


def categorize_ollama_batch_with_trace(
    rows: List[Dict[str, str]],
    ollama_url: str,
    model: str,
    categories: List[str],
    prompt_template: str = DEFAULT_OLLAMA_BATCH_PROMPT_TEMPLATE,
    temperature: float = 0.0,
    timeout: float = 60.0,
) -> Dict[str, object]:
    prompt, row_ids = build_ollama_batch_prompt(rows, categories, prompt_template=prompt_template)
    text = request_ollama_response(
        prompt=prompt,
        ollama_url=ollama_url,
        model=model,
        temperature=temperature,
        timeout=timeout,
    )
    assigned = _parse_ollama_batch_response(text, categories, row_ids)
    return {"categories": assigned, "row_ids": row_ids, "prompt": prompt, "response": text}


def build_ollama_prompt(row: Dict[str, str], categories: List[str], prompt_template: str) -> str:
    return _build_prompt(row, categories, prompt_template=prompt_template)


def build_ollama_batch_prompt(rows: List[Dict[str, str]], categories: List[str], prompt_template: str) -> tuple[str, List[str]]:
    template = (prompt_template or "").strip() or DEFAULT_OLLAMA_BATCH_PROMPT_TEMPLATE
    row_ids: List[str] = []
    payload_rows: List[Dict[str, str]] = []
    for idx, row in enumerate(rows, 1):
        row_id = str(idx)
        row_ids.append(row_id)
        payload_rows.append(
            {
                "row_id": row_id,
                "date": row.get("date", ""),
                "amount": row.get("amount", ""),
                "description": row.get("description", ""),
                "notes": row.get("notes", ""),
                "tags": row.get("tags", ""),
                "type": row.get("type", ""),
                "source_account": row.get("source_account", ""),
                "destination_account": row.get("destination_account", ""),
                "current_category": row.get("category", ""),
            }
        )

    context = {
        "categories_csv": ", ".join(categories),
        "categories_json": json.dumps(categories, ensure_ascii=True),
        "transactions_json": json.dumps(payload_rows, ensure_ascii=True),
    }
    try:
        return template.format_map(context), row_ids
    except Exception:
        return DEFAULT_OLLAMA_BATCH_PROMPT_TEMPLATE.format_map(context), row_ids


def request_ollama_response(
    prompt: str,
    ollama_url: str,
    model: str,
    temperature: float = 0.0,
    timeout: float = 60.0,
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    response = requests.post(
        f"{ollama_url.rstrip('/')}/api/generate",
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    return (data.get("response") or "").strip()


def _build_prompt(row: Dict[str, str], categories: List[str], prompt_template: str) -> str:
    cats = ", ".join(categories)
    txn = {
        "date": row.get("date", ""),
        "amount": row.get("amount", ""),
        "description": row.get("description", ""),
        "notes": row.get("notes", ""),
        "tags": row.get("tags", ""),
        "type": row.get("type", ""),
        "source_account": row.get("source_account", ""),
        "destination_account": row.get("destination_account", ""),
    }
    template = (prompt_template or "").strip() or DEFAULT_OLLAMA_PROMPT_TEMPLATE
    context = {
        "categories_csv": cats,
        "categories_json": json.dumps(categories, ensure_ascii=True),
        "transaction_json": json.dumps(txn, ensure_ascii=True),
    }
    try:
        return template.format_map(context)
    except Exception:
        return DEFAULT_OLLAMA_PROMPT_TEMPLATE.format_map(context)


def _parse_ollama_response(text: str, categories: List[str]) -> str:
    allowed = {c.strip() for c in categories if c.strip()}
    raw = (text or "").strip()
    if not raw:
        return "Other"

    try:
        obj = json.loads(raw)
        category = str(obj.get("category") or "").strip()
        if category in allowed:
            return category
    except json.JSONDecodeError:
        pass

    for category in allowed:
        if raw.lower() == category.lower():
            return category
    return "Other"


def _parse_ollama_batch_response(text: str, categories: List[str], row_ids: List[str]) -> List[str]:
    assigned = {rid: "Other" for rid in row_ids}
    allowed = [c.strip() for c in categories if c and c.strip()]
    allowed_map = {item.lower(): item for item in allowed}
    raw = (text or "").strip()
    if not raw:
        return [assigned[rid] for rid in row_ids]

    def normalize_category(token: object) -> str:
        candidate = str(token or "").strip()
        if not candidate:
            return "Other"
        return allowed_map.get(candidate.lower(), "Other")

    def normalize_row_id(token: object) -> str:
        value = str(token or "").strip()
        if value.isdigit():
            idx = int(value)
            if 1 <= idx <= len(row_ids):
                return row_ids[idx - 1]
        if value in assigned:
            return value
        return ""

    items: List[Dict[str, object]] = []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            embedded = parsed.get("items")
            if isinstance(embedded, list):
                items = [entry for entry in embedded if isinstance(entry, dict)]
        elif isinstance(parsed, list):
            items = [entry for entry in parsed if isinstance(entry, dict)]
    except json.JSONDecodeError:
        items = []

    for entry in items:
        row_id = normalize_row_id(entry.get("row_id") or entry.get("id") or entry.get("index"))
        if not row_id:
            continue
        assigned[row_id] = normalize_category(entry.get("category"))

    return [assigned[rid] for rid in row_ids]
