"""
AI Engine — powered by Anthropic Claude
========================================
Two public functions:

  categorise_batch(transactions)
      Sends up to 50 transactions in a single prompt and returns a
      category name + confidence score for each one.

  generate_insights(summary_data)
      Produces a natural-language financial health report: spending
      patterns, anomalies, and actionable suggestions.

Both functions are designed to be called from the routers layer after
transactions are persisted to the database.
"""
import json
import os
from decimal import Decimal

import anthropic

# ── Client ─────────────────────────────────────────────────────────────────────

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Must match the seeded category names in the migration exactly
VALID_CATEGORIES = [
    "Salary & Wages", "Transfer In", "Food & Dining", "Transport",
    "Utilities", "Rent & Housing", "Health & Medical", "Shopping",
    "Entertainment", "Education", "Savings & Investment", "Transfer Out", "Other",
]


# ── Categorisation ─────────────────────────────────────────────────────────────

def categorise_batch(transactions: list[dict]) -> list[dict]:
    """
    Given a list of transaction dicts (id, description, amount, type),
    return a list of {id, category, confidence} dicts.

    Batches up to 50 items per API call to stay within token limits.
    """
    results = []
    batch_size = 50

    for i in range(0, len(transactions), batch_size):
        batch = transactions[i : i + batch_size]
        results.extend(_categorise_single_batch(batch))

    return results


def _categorise_single_batch(batch: list[dict]) -> list[dict]:
    """Send one batch to Claude and parse the JSON response."""
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

    message = _client.messages.create(
        model="claude-haiku-4-5-20251001",   # fast + cheap for bulk classification
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if Claude wraps the JSON
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        parsed = json.loads(raw)
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

    message = _client.messages.create(
        model="claude-sonnet-5",    # stronger model for nuanced narrative
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text.strip()


# ── Anomaly detection helper ───────────────────────────────────────────────────

def detect_anomalies(transactions: list[dict]) -> list[dict]:
    """
    Ask Claude to flag transactions that look unusual compared to the rest
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

    message = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []
