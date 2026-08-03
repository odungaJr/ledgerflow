"""
AI Engine — powered by a local Ollama model
============================================
Three public functions:

  categorise_batch(transactions)
      Sends up to 50 transactions in a single prompt and returns a
      category name + confidence score for each one.

  generate_insights(summary_data)
      Produces a natural-language financial health report: spending
      patterns, anomalies, and actionable suggestions.

  detect_anomalies(transactions)
      Flags transactions that look unusual (outlier amounts, odd timing,
      suspicious descriptions).

All three call a locally-running Ollama server instead of a paid API —
no billing, no API key, and financial data never leaves the machine.
OLLAMA_BASE_URL defaults to the native host install (localhost); when the
backend itself runs inside Docker it's overridden to
`http://host.docker.internal:11434` (see docker-compose.yml) since
"localhost" inside a container means the container, not the Mac host.

Both functions are designed to be called from the routers layer after
transactions are persisted to the database.
"""
import json
import os
import urllib.request
from decimal import Decimal

# ── Client ─────────────────────────────────────────────────────────────────────

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")

# Must match the seeded category names in the migration exactly
VALID_CATEGORIES = [
    "Salary & Wages", "Transfer In", "Food & Dining", "Transport",
    "Utilities", "Rent & Housing", "Health & Medical", "Shopping",
    "Entertainment", "Education", "Savings & Investment", "Transfer Out", "Other",
]


def _ollama_chat(prompt: str, *, json_mode: bool = False, timeout: int = 240) -> str:
    """Send a single-turn prompt to the local Ollama server, return the reply text.

    Raises urllib.error.URLError (e.g. connection refused if Ollama isn't
    running) or TimeoutError on a slow response — callers already treat any
    AI-engine exception as a soft failure, so these aren't caught here.
    """
    body = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        # Keep the model loaded between calls so a call shortly after the
        # last one doesn't pay for a cold model load (multi-GB, can take
        # long enough under system load to blow past the timeout) on top of
        # actual inference. Ollama's own default is 5m; this just widens it
        # for a more forgiving margin during an active session.
        "keep_alive": "30m",
    }
    if json_mode:
        body["format"] = "json"  # constrains generation to valid JSON

    request = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        parsed = json.loads(response.read())
    return parsed["message"]["content"].strip()


def _strip_code_fence(raw: str) -> str:
    """Some models wrap JSON output in ``` fences despite instructions not to."""
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw


def _coerce_to_list(parsed) -> list:
    """A requested top-level JSON array sometimes comes back shaped
    differently — observed with qwen2.5 even under a strict array JSON
    schema:
      - wrapped in an object, e.g. {"transactions": [...]}
      - collapsed into a single bare object instead of a one-item array,
        e.g. {"id": 1, "category": "...", "confidence": 0.9} when the
        model apparently felt confident enough to skip the array wrapper
    Recover both rather than fighting the model's formatting instincts."""
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for value in parsed.values():
            if isinstance(value, list):
                return value
        if parsed:
            return [parsed]
    return []


# ── Categorisation ─────────────────────────────────────────────────────────────

def categorise_batch(transactions: list[dict]) -> list[dict]:
    """
    Given a list of transaction dicts (id, description, amount, type),
    return a list of {id, category, confidence} dicts.

    Batches up to 50 items per call to stay within a reasonable prompt size.
    """
    results = []
    batch_size = 50

    for i in range(0, len(transactions), batch_size):
        batch = transactions[i : i + batch_size]
        results.extend(_categorise_single_batch(batch))

    return results


def _categorise_single_batch(batch: list[dict]) -> list[dict]:
    """Send one batch to the model and parse the JSON response."""
    lines = "\n".join(
        f"{idx+1}. [{t['type'].upper()}] {t['description']} — {t['amount']}"
        for idx, t in enumerate(batch)
    )

    prompt = f"""You are a personal finance categoriser for an East African user (Tanzania).

Assign each transaction below exactly one category from this list:
{', '.join(VALID_CATEGORIES)}

Rules:
- Mobile money (M-Pesa, Tigo Pesa, Airtel Money) peer-to-peer transfers out → "Transfer Out"
- Mobile money received → "Transfer In"
- Employer/payroll deposits → "Salary & Wages"
- ATM withdrawals without a merchant → "Other"
- Be conservative with confidence: use < 0.7 when the description is ambiguous

Return ONLY a JSON array, one object per transaction, in order:
[{{"id": <1-based index>, "category": "...", "confidence": 0.00}}, ...]

Transactions:
{lines}"""

    raw = _strip_code_fence(_ollama_chat(prompt, json_mode=True))

    try:
        parsed = _coerce_to_list(json.loads(raw))
    except json.JSONDecodeError:
        # Malformed response — skip this batch rather than failing the whole import.
        return []

    results = []
    for item in parsed:
        idx = int(item["id"]) - 1
        if idx < 0 or idx >= len(batch):
            continue
        results.append({
            "transaction_id": batch[idx].get("id"),
            "category":       item.get("category", "Other"),
            "confidence":     float(item.get("confidence", 0.5)),
        })

    return results


# ── Insights generation ────────────────────────────────────────────────────────

def generate_insights(summary: dict) -> str:
    """
    Produce a natural-language financial health report.

    `summary` should contain:
      - period:         e.g. "April 2026"
      - total_income:   Decimal / float
      - total_expenses: Decimal / float
      - net:            Decimal / float
      - currency:       e.g. "TZS"
      - top_categories: list of {name, total, budget_limit (optional)}
      - anomalies:      list of {description, amount, reason}  (can be empty)
    """
    # Convert Decimals to strings so json.dumps doesn't choke
    def _serialise(obj):
        if isinstance(obj, Decimal):
            return str(obj)
        raise TypeError(f"Not serialisable: {type(obj)}")

    summary_json = json.dumps(summary, default=_serialise, indent=2)

    prompt = f"""You are a personal finance advisor helping an individual in Tanzania understand their spending.

Here is their financial summary for {summary.get('period', 'the selected period')}:

{summary_json}

Write a concise, friendly financial insights report (200–300 words). Structure it as:

1. **Overview** — one sentence on overall financial health.
2. **Key Spending Patterns** — what stands out in their top categories.
3. **Budget Alerts** — highlight any category that exceeded or is close to its budget limit.
4. **Anomalies** — flag unusual transactions if any were detected.
5. **Suggestions** — 2–3 practical, actionable tips tailored to their actual spending.

Write in plain English. Be specific with numbers. Avoid generic advice."""

    return _ollama_chat(prompt)


# ── Anomaly detection helper ───────────────────────────────────────────────────

def detect_anomalies(transactions: list[dict]) -> list[dict]:
    """
    Ask the model to flag transactions that look unusual compared to the rest
    of the batch (e.g. outlier amounts, odd timing, suspicious descriptions).

    Returns a list of {transaction_id, reason} dicts.
    """
    if not transactions:
        return []

    lines = "\n".join(
        f"{t['date']} | {t['description']} | {t['type'].upper()} | {t['amount']}"
        for t in transactions
    )

    prompt = f"""You are a fraud and anomaly detection assistant for a personal bank account.

Review the transactions below and flag any that look unusual. Reasons could include:
- Amount is far larger or smaller than typical for the merchant type
- Duplicate-looking entries on the same day
- Suspicious merchant names or patterns
- Timing anomalies (e.g. 3am transactions)

Return ONLY a JSON array of flagged items:
[{{"description": "...", "date": "...", "amount": "...", "reason": "..."}}]

If nothing is suspicious, return: []

Transactions:
{lines}"""

    raw = _strip_code_fence(_ollama_chat(prompt, json_mode=True))

    try:
        return _coerce_to_list(json.loads(raw))
    except json.JSONDecodeError:
        return []
