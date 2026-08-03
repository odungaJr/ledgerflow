"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  createIncomeEntry,
  deleteIncomeEntry,
  getCategories,
  getIncomeEntries,
  getIncomeSummary,
  getIncomeSummaryAllTime,
  patchIncomeEntry,
} from "@/lib/api";
import { todayIso } from "@/lib/date";
import { formatDate, formatMoney } from "@/lib/format";
import type { Category, IncomeEntry, IncomeSummary } from "@/lib/types";

const STATUS_BADGE: Record<IncomeEntry["status"], string> = {
  received: "ok",
  partial: "warning",
  overdue: "danger",
  pending: "neutral",
};

const STATUS_LABEL: Record<IncomeEntry["status"], string> = {
  received: "Received",
  partial: "Partially received",
  overdue: "Overdue",
  pending: "Pending",
};

export default function IncomePage() {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);

  const [entries, setEntries] = useState<IncomeEntry[]>([]);
  const [summary, setSummary] = useState<IncomeSummary | null>(null);
  const [allTimeSummary, setAllTimeSummary] = useState<IncomeSummary | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [source, setSource] = useState("");
  const [categoryName, setCategoryName] = useState("");
  const [expectedAmount, setExpectedAmount] = useState("");
  const [expectedDate, setExpectedDate] = useState(todayIso());
  const [isRecurring, setIsRecurring] = useState(false);
  const [recurrencePeriod, setRecurrencePeriod] = useState<"monthly" | "weekly">("monthly");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editReceived, setEditReceived] = useState("");
  const [editReceivedDate, setEditReceivedDate] = useState(todayIso());

  function load() {
    setLoading(true);
    getIncomeEntries(year, month)
      .then((data) => {
        setEntries(data);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load income entries"))
      .finally(() => setLoading(false));
    getIncomeSummary(year, month).then(setSummary).catch(() => {});
    getIncomeSummaryAllTime().then(setAllTimeSummary).catch(() => {});
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year, month]);

  useEffect(() => {
    getCategories()
      .then((cats) => setCategories(cats.filter((c) => c.is_income)))
      .catch(() => {
        // Categories are a convenience for the dropdown — the form still works without them.
      });
  }, []);

  function changeMonth(delta: number) {
    let newMonth = month + delta;
    let newYear = year;
    if (newMonth < 1) {
      newMonth = 12;
      newYear -= 1;
    } else if (newMonth > 12) {
      newMonth = 1;
      newYear += 1;
    }
    setMonth(newMonth);
    setYear(newYear);
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    const amount = Number(expectedAmount);
    if (!source.trim() || !amount || amount <= 0) {
      setFormError("Enter a source and an expected amount greater than zero.");
      return;
    }
    setSubmitting(true);
    try {
      await createIncomeEntry({
        source: source.trim(),
        expected_amount: amount,
        expected_date: expectedDate,
        category_name: categoryName || undefined,
        is_recurring: isRecurring,
        recurrence_period: isRecurring ? recurrencePeriod : undefined,
      });
      setSource("");
      setExpectedAmount("");
      setIsRecurring(false);
      load();
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Failed to create income entry");
    } finally {
      setSubmitting(false);
    }
  }

  function startEdit(entry: IncomeEntry) {
    setEditingId(entry.id);
    setEditReceived(String(entry.received_amount || ""));
    setEditReceivedDate(entry.received_date || todayIso());
  }

  async function saveEdit(id: string) {
    const amount = Number(editReceived);
    if (Number.isNaN(amount) || amount < 0) return;
    await patchIncomeEntry(id, { received_amount: amount, received_date: editReceivedDate });
    setEditingId(null);
    load();
  }

  async function handleDelete(entry: IncomeEntry) {
    if (!confirm(`Delete "${entry.source}"?`)) return;
    await deleteIncomeEntry(entry.id);
    load();
  }

  const periodLabel = new Date(year, month - 1, 1).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });

  return (
    <main className="page">
      <div className="container">
        <div className="pageHeader">
          <h1>Income Tracker</h1>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <button className="btn btnSecondary btnSmall" onClick={() => changeMonth(-1)}>
              ‹
            </button>
            <span className="badge neutral">{periodLabel}</span>
            <button className="btn btnSecondary btnSmall" onClick={() => changeMonth(1)}>
              ›
            </button>
          </div>
        </div>

        {allTimeSummary && (
          <div className="spacer">
            <h2 className="sectionTitle">All-time</h2>
            <div className="grid">
              <div className="card">
                <p className="statLabel">Received to date</p>
                <p className="statValue positive">{formatMoney(allTimeSummary.total_received)}</p>
              </div>
              <div className="card">
                <p className="statLabel">Pending to date</p>
                <p className={`statValue ${allTimeSummary.total_pending > 0 ? "negative" : "positive"}`}>
                  {formatMoney(allTimeSummary.total_pending)}
                </p>
                {allTimeSummary.overdue_count > 0 && (
                  <span className="badge danger" style={{ marginTop: "0.5rem", display: "inline-block" }}>
                    {allTimeSummary.overdue_count} overdue
                  </span>
                )}
              </div>
              <div className="card">
                <p className="statLabel">Expected to date</p>
                <p className="statValue">{formatMoney(allTimeSummary.total_expected)}</p>
              </div>
            </div>
          </div>
        )}

        {summary && (
          <div className="spacer">
            <h2 className="sectionTitle">{periodLabel}</h2>
            <div className="grid">
              <div className="card">
                <p className="statLabel">Expected</p>
                <p className="statValue">{formatMoney(summary.total_expected)}</p>
              </div>
              <div className="card">
                <p className="statLabel">Received</p>
                <p className="statValue positive">{formatMoney(summary.total_received)}</p>
              </div>
              <div className="card">
                <p className="statLabel">Pending</p>
                <p className={`statValue ${summary.total_pending > 0 ? "negative" : "positive"}`}>
                  {formatMoney(summary.total_pending)}
                </p>
                {summary.overdue_count > 0 && (
                  <span className="badge danger" style={{ marginTop: "0.5rem", display: "inline-block" }}>
                    {summary.overdue_count} overdue
                  </span>
                )}
              </div>
            </div>
          </div>
        )}

        <form className="form" onSubmit={handleCreate}>
          <h2 className="sectionTitle">Add expected income</h2>
          <div className="formInline">
            <div className="formRow">
              <label htmlFor="income-source">Source</label>
              <input
                id="income-source"
                value={source}
                onChange={(e) => setSource(e.target.value)}
                placeholder="Salary — Company X"
                required
              />
            </div>
            <div className="formRow">
              <label htmlFor="income-category">Category (optional)</label>
              <select
                id="income-category"
                value={categoryName}
                onChange={(e) => setCategoryName(e.target.value)}
              >
                <option value="">None</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.name}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="formRow">
              <label htmlFor="income-amount">Expected amount</label>
              <input
                id="income-amount"
                type="number"
                min="1"
                step="0.01"
                value={expectedAmount}
                onChange={(e) => setExpectedAmount(e.target.value)}
                placeholder="500000"
                required
              />
            </div>
            <div className="formRow" style={{ maxWidth: "160px" }}>
              <label htmlFor="income-date">Expected date</label>
              <input
                id="income-date"
                type="date"
                value={expectedDate}
                onChange={(e) => setExpectedDate(e.target.value)}
              />
            </div>
            <div className="formRow" style={{ maxWidth: "160px" }}>
              <label htmlFor="income-recurring">Recurring?</label>
              <select
                id="income-recurring"
                value={isRecurring ? recurrencePeriod : "none"}
                onChange={(e) => {
                  if (e.target.value === "none") {
                    setIsRecurring(false);
                  } else {
                    setIsRecurring(true);
                    setRecurrencePeriod(e.target.value as "monthly" | "weekly");
                  }
                }}
              >
                <option value="none">One-off</option>
                <option value="monthly">Monthly</option>
                <option value="weekly">Weekly</option>
              </select>
            </div>
            <button className="btn" type="submit" disabled={submitting}>
              {submitting ? "Adding…" : "Add income"}
            </button>
          </div>
          {formError && <div className="alert error">{formError}</div>}
        </form>

        <div className="spacer">
          {loading && <p>Loading…</p>}
          {error && <div className="alert error">{error}</div>}
          {!loading && !error && entries.length === 0 && (
            <div className="empty">No income entries for {periodLabel} — add one above.</div>
          )}
          {!loading && entries.length > 0 && (
            <div className="grid">
              {entries.map((entry) => (
                <div className="card" key={entry.id}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div>
                      <p className="statLabel" style={{ margin: 0 }}>
                        {entry.source}
                        {entry.is_recurring && ` · Recurring (${entry.recurrence_period})`}
                      </p>
                      {entry.category && (
                        <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", margin: 0 }}>
                          {entry.category}
                        </p>
                      )}
                    </div>
                    <span className={`badge ${STATUS_BADGE[entry.status]}`}>{STATUS_LABEL[entry.status]}</span>
                  </div>

                  <p style={{ marginTop: "0.6rem", fontSize: "0.85rem", color: "var(--text-muted)" }}>
                    Expected {formatDate(entry.expected_date)} · {formatMoney(entry.expected_amount)}
                  </p>
                  <p style={{ fontSize: "0.85rem" }}>
                    Received {formatMoney(entry.received_amount)}
                    {entry.pending_amount > 0 && (
                      <> · <span style={{ color: "var(--danger)" }}>{formatMoney(entry.pending_amount)} pending</span></>
                    )}
                  </p>

                  {editingId === entry.id ? (
                    <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.6rem", flexWrap: "wrap" }}>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={editReceived}
                        onChange={(e) => setEditReceived(e.target.value)}
                        style={{ maxWidth: "140px" }}
                      />
                      <input
                        type="date"
                        value={editReceivedDate}
                        onChange={(e) => setEditReceivedDate(e.target.value)}
                        style={{ maxWidth: "160px" }}
                      />
                      <button className="btn btnSmall" onClick={() => saveEdit(entry.id)}>
                        Save
                      </button>
                      <button className="btn btnSecondary btnSmall" onClick={() => setEditingId(null)}>
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.75rem" }}>
                      <button className="btn btnSecondary btnSmall" onClick={() => startEdit(entry)}>
                        Record received
                      </button>
                      <button className="btn btnDanger btnSmall" onClick={() => handleDelete(entry)}>
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
