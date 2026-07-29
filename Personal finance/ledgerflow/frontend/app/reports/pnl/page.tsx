"use client";

import { useEffect, useState } from "react";
import { ApiError, getPnl } from "@/lib/api";
import { dateToIso, todayIso } from "@/lib/date";
import { formatMoney } from "@/lib/format";
import type { PnlStatement } from "@/lib/types";

type PresetKey = "this_month" | "last_month" | "this_year" | "all_time" | "custom";

function presetRange(key: PresetKey): { from: string; to: string } {
  const today = new Date();
  const y = today.getFullYear();
  const m = today.getMonth();

  switch (key) {
    case "this_month":
      return { from: dateToIso(new Date(y, m, 1)), to: todayIso() };
    case "last_month":
      return { from: dateToIso(new Date(y, m - 1, 1)), to: dateToIso(new Date(y, m, 0)) };
    case "this_year":
      return { from: dateToIso(new Date(y, 0, 1)), to: todayIso() };
    case "all_time":
      return { from: "2000-01-01", to: todayIso() };
    default:
      return { from: dateToIso(new Date(y, m, 1)), to: todayIso() };
  }
}

const PRESETS: { key: PresetKey; label: string }[] = [
  { key: "this_month", label: "This month" },
  { key: "last_month", label: "Last month" },
  { key: "this_year", label: "This year" },
  { key: "all_time", label: "All-time" },
];

export default function PnlPage() {
  const [preset, setPreset] = useState<PresetKey>("this_month");
  const [fromDate, setFromDate] = useState(() => presetRange("this_month").from);
  const [toDate, setToDate] = useState(() => presetRange("this_month").to);
  const [statement, setStatement] = useState<PnlStatement | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function applyPreset(key: PresetKey) {
    setPreset(key);
    const { from, to } = presetRange(key);
    setFromDate(from);
    setToDate(to);
  }

  useEffect(() => {
    setLoading(true);
    getPnl(fromDate, toDate)
      .then((data) => {
        setStatement(data);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load P&L statement"))
      .finally(() => setLoading(false));
  }, [fromDate, toDate]);

  function handleExportCsv() {
    if (!statement) return;
    const lines: string[] = ["Section,Category,Amount"];
    for (const row of statement.income) lines.push(`Income,${row.name},${row.total}`);
    for (const row of statement.expenses) lines.push(`Expense,${row.name},${row.total}`);
    lines.push(`,Total Income,${statement.total_income}`);
    lines.push(`,Total Expenses,${statement.total_expenses}`);
    lines.push(`,Net Income,${statement.net_income}`);

    const blob = new Blob([lines.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `pnl_${statement.from_date}_to_${statement.to_date}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="page">
      <div className="container">
        <div className="pageHeader">
          <h1>P&amp;L Statement</h1>
          <button className="btn btnSecondary btnSmall" onClick={handleExportCsv} disabled={!statement}>
            Export CSV
          </button>
        </div>

        <div className="card">
          <div className="formInline">
            {PRESETS.map((p) => (
              <button
                key={p.key}
                type="button"
                className={`btn btnSmall ${preset === p.key ? "" : "btnSecondary"}`}
                onClick={() => applyPreset(p.key)}
              >
                {p.label}
              </button>
            ))}
          </div>
          <div className="spacer" />
          <div className="formInline">
            <div className="formRow">
              <label htmlFor="pnl-from">From</label>
              <input
                id="pnl-from"
                type="date"
                value={fromDate}
                onChange={(e) => {
                  setPreset("custom");
                  setFromDate(e.target.value);
                }}
              />
            </div>
            <div className="formRow">
              <label htmlFor="pnl-to">To</label>
              <input
                id="pnl-to"
                type="date"
                value={toDate}
                onChange={(e) => {
                  setPreset("custom");
                  setToDate(e.target.value);
                }}
              />
            </div>
          </div>
        </div>

        <div className="spacer" />

        {loading ? (
          <p>Loading…</p>
        ) : error ? (
          <div className="alert error">{error}</div>
        ) : statement ? (
          <>
            <div className="grid">
              <div className="card">
                <p className="statLabel">Total income</p>
                <p className="statValue positive">{formatMoney(statement.total_income, statement.currency)}</p>
              </div>
              <div className="card">
                <p className="statLabel">Total expenses</p>
                <p className="statValue negative">{formatMoney(statement.total_expenses, statement.currency)}</p>
              </div>
              <div className="card">
                <p className="statLabel">Net income</p>
                <p className={`statValue ${statement.net_income >= 0 ? "positive" : "negative"}`}>
                  {formatMoney(statement.net_income, statement.currency)}
                </p>
              </div>
            </div>

            <div className="spacer" />

            <h2 className="sectionTitle">Income by category</h2>
            <PnlTable rows={statement.income} currency={statement.currency} emptyLabel="No income in this period." />

            <div className="spacer" />

            <h2 className="sectionTitle">Expenses by category</h2>
            <PnlTable rows={statement.expenses} currency={statement.currency} emptyLabel="No expenses in this period." />
          </>
        ) : null}
      </div>
    </main>
  );
}

function PnlTable({
  rows,
  currency,
  emptyLabel,
}: {
  rows: PnlStatement["income"];
  currency: string;
  emptyLabel: string;
}) {
  if (rows.length === 0) {
    return <div className="empty">{emptyLabel}</div>;
  }
  const total = rows.reduce((sum, r) => sum + r.total, 0);

  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>Category</th>
            <th>Amount</th>
            <th>% of total</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name}>
              <td data-label="Category">
                {r.icon} {r.name}
              </td>
              <td data-label="Amount">{formatMoney(r.total, currency)}</td>
              <td data-label="% of total">{total > 0 ? `${((r.total / total) * 100).toFixed(1)}%` : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
