"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Sparkline from "@/components/Sparkline";
import { ApiError, getDashboardInsights, getDashboardSummary, getIncomeEntries, getTransactions } from "@/lib/api";
import { dateToIso } from "@/lib/date";
import { formatMoney } from "@/lib/format";
import type { DashboardSummaryResponse } from "@/lib/types";

function formatAssetType(assetType: string): string {
  const label = assetType.replace(/_/g, " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export default function DashboardPage() {
  const router = useRouter();
  const [year, setYear] = useState<number | null>(null);
  const [month, setMonth] = useState<number | null>(null);

  const [data, setData] = useState<DashboardSummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [narrative, setNarrative] = useState<string | null>(null);
  const [insightsError, setInsightsError] = useState<string | null>(null);
  const [insightsLoading, setInsightsLoading] = useState(false);

  // Default to whichever is more recent — the latest bank transaction or the
  // latest logged income entry — rather than transactions alone. Otherwise,
  // logging income for the current month while bank statements are older
  // (or vice versa) silently shows the wrong period's figures with no
  // indication the two don't match.
  useEffect(() => {
    Promise.all([
      getTransactions({ limit: 1 }).catch(() => []),
      getIncomeEntries().catch(() => []),
    ]).then(([txns, income]) => {
      const dates = [
        ...txns.map((t) => t.date),
        ...income.map((i) => i.expected_date),
      ];
      const ref = dates.length > 0
        ? new Date(dates.reduce((latest, d) => (d > latest ? d : latest)))
        : new Date();
      setYear(ref.getFullYear());
      setMonth(ref.getMonth() + 1);
    });
  }, []);

  useEffect(() => {
    if (year == null || month == null) return;
    setLoading(true);
    setNarrative(null);
    setInsightsError(null);
    getDashboardSummary(year, month)
      .then((res) => {
        setData(res);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load dashboard"))
      .finally(() => setLoading(false));
  }, [year, month]);

  function changeMonth(delta: number) {
    if (year == null || month == null) return;
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

  async function handleGenerateInsights() {
    if (year == null || month == null) return;
    setInsightsLoading(true);
    setInsightsError(null);
    try {
      const res = await getDashboardInsights(year, month);
      setNarrative(res.narrative);
    } catch (e) {
      setInsightsError(
        e instanceof ApiError
          ? e.message
          : "Could not generate insights — the AI service may be unavailable."
      );
    } finally {
      setInsightsLoading(false);
    }
  }

  const currency = data?.summary.currency ?? "TZS";
  const periodLabel =
    year != null && month != null
      ? new Date(year, month - 1, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" })
      : "";

  function categoryDrilldownUrl(categoryName: string): string | null {
    if (year == null || month == null) return null;
    const from = `${year}-${String(month).padStart(2, "0")}-01`;
    const to = dateToIso(new Date(year, month, 0));
    const qs = new URLSearchParams({ category: categoryName, from_date: from, to_date: to });
    return `/transactions?${qs.toString()}`;
  }

  return (
    <main className="page">
      <div className="container">
        <div className="pageHeader">
          <h1>Dashboard</h1>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <button className="btn btnSecondary btnSmall" onClick={() => changeMonth(-1)} disabled={year == null}>
              ‹
            </button>
            {periodLabel && <span className="badge neutral">{periodLabel}</span>}
            <button className="btn btnSecondary btnSmall" onClick={() => changeMonth(1)} disabled={year == null}>
              ›
            </button>
          </div>
        </div>

        {loading && <p>Loading…</p>}
        {error && <div className="alert error">{error}</div>}

        {data && (
          <>
            <div className="grid">
              <div className="card">
                <p className="statLabel">Income</p>
                <p className="statValue positive">
                  {formatMoney(data.summary.total_income, currency)}
                </p>
              </div>
              <div className="card">
                <p className="statLabel">Expenses</p>
                <p className="statValue negative">
                  {formatMoney(data.summary.total_expenses, currency)}
                </p>
              </div>
              <div className="card">
                <p className="statLabel">Net</p>
                <p className={`statValue ${data.summary.net >= 0 ? "positive" : "negative"}`}>
                  {formatMoney(data.summary.net, currency)}
                </p>
              </div>
            </div>

            {data.budget_alerts.length > 0 && (
              <div className="spacer">
                <h2 className="sectionTitle">Budget alerts</h2>
                <div className="grid">
                  {data.budget_alerts.map((b) => {
                    const url = categoryDrilldownUrl(b.category_name);
                    return (
                      <Link
                        href={url ?? "/transactions"}
                        className="card"
                        key={b.budget_id}
                        style={{ display: "block", textDecoration: "none", color: "inherit" }}
                      >
                        <p className="statLabel">{b.category_name}</p>
                        <span className={`badge ${b.is_breached ? "danger" : "warning"}`}>
                          {b.is_breached ? "Over budget" : "Near limit"}
                        </span>
                        <div className="spacer" style={{ marginTop: "0.6rem" }}>
                          <div className="progress">
                            <div
                              className={`progressFill ${b.is_breached ? "danger" : "warning"}`}
                              style={{ width: `${Math.min(b.pct_used * 100, 100)}%` }}
                            />
                          </div>
                        </div>
                        <p style={{ marginTop: "0.5rem", fontSize: "0.85rem", color: "var(--text-muted)" }}>
                          {formatMoney(b.spent, currency)} of {formatMoney(b.limit, currency)}
                        </p>
                      </Link>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="spacer">
              <h2 className="sectionTitle">Top categories</h2>
              {data.summary.top_categories.length === 0 ? (
                <div className="empty">No categorised spending yet this period.</div>
              ) : (
                <div className="tableWrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Category</th>
                        <th>Spent</th>
                        <th>Budget</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.summary.top_categories.map((c) => (
                        <tr
                          key={c.name}
                          onClick={() => {
                            const url = categoryDrilldownUrl(c.name);
                            if (url) router.push(url);
                          }}
                          style={{ cursor: "pointer" }}
                        >
                          <td data-label="Category">{c.name}</td>
                          <td data-label="Spent">{formatMoney(c.total, currency)}</td>
                          <td data-label="Budget">
                            {c.budget_limit != null ? formatMoney(c.budget_limit, currency) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="spacer">
              <h2 className="sectionTitle">Income tracker</h2>
              <div className="grid">
                <div className="card">
                  <p className="statLabel">Expected</p>
                  <p className="statValue">{formatMoney(data.income_tracker.total_expected, currency)}</p>
                </div>
                <div className="card">
                  <p className="statLabel">Received</p>
                  <p className="statValue positive">
                    {formatMoney(data.income_tracker.total_received, currency)}
                  </p>
                </div>
                <div className="card">
                  <p className="statLabel">Pending</p>
                  <p className={`statValue ${data.income_tracker.total_pending > 0 ? "negative" : "positive"}`}>
                    {formatMoney(data.income_tracker.total_pending, currency)}
                  </p>
                  {data.income_tracker.overdue_count > 0 && (
                    <Link href="/income" style={{ marginTop: "0.5rem", display: "inline-block" }}>
                      <span className="badge danger">{data.income_tracker.overdue_count} overdue</span>
                    </Link>
                  )}
                </div>
              </div>

              <p className="statLabel" style={{ marginTop: "1rem" }}>
                All-time
              </p>
              <div className="grid" style={{ marginTop: "0.4rem" }}>
                <div className="card">
                  <p className="statLabel">Received to date</p>
                  <p className="statValue positive">
                    {formatMoney(data.income_all_time.total_received, currency)}
                  </p>
                </div>
                <div className="card">
                  <p className="statLabel">Pending to date</p>
                  <p className={`statValue ${data.income_all_time.total_pending > 0 ? "negative" : "positive"}`}>
                    {formatMoney(data.income_all_time.total_pending, currency)}
                  </p>
                  {data.income_all_time.overdue_count > 0 && (
                    <Link href="/income" style={{ marginTop: "0.5rem", display: "inline-block" }}>
                      <span className="badge danger">{data.income_all_time.overdue_count} overdue</span>
                    </Link>
                  )}
                </div>
              </div>

              <p style={{ marginTop: "0.6rem", fontSize: "0.85rem" }}>
                <Link href="/income">Manage income entries →</Link>
              </p>
            </div>

            <div className="spacer">
              <h2 className="sectionTitle">Net worth</h2>
              <div className="grid">
                <div className="card">
                  <p className="statLabel">Total assets</p>
                  <p className="statValue">{formatMoney(data.assets.total_value)}</p>
                </div>
              </div>

              {data.assets.breakdown.length > 0 && (
                <div className="tableWrap spacer">
                  <table>
                    <thead>
                      <tr>
                        <th>Type</th>
                        <th>Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.assets.breakdown.map((row) => (
                        <tr key={row.asset_type} onClick={() => router.push("/assets")} style={{ cursor: "pointer" }}>
                          <td data-label="Type">{formatAssetType(row.asset_type)}</td>
                          <td data-label="Value">{formatMoney(row.total)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {data.assets.assets.length === 0 ? (
                <div className="empty spacer">No assets tracked yet.</div>
              ) : (
                <div className="card spacer">
                  <p className="statLabel">Value trend</p>
                  <Sparkline data={data.assets.trend} />
                </div>
              )}

              <p style={{ marginTop: "0.6rem", fontSize: "0.85rem" }}>
                <Link href="/assets">Manage assets →</Link>
              </p>
            </div>

            <div className="spacer">
              <h2 className="sectionTitle">AI insights</h2>
              <button className="btn" onClick={handleGenerateInsights} disabled={insightsLoading}>
                {insightsLoading ? "Generating…" : "Generate insights"}
              </button>
              {insightsError && (
                <div className="alert error" style={{ marginTop: "0.75rem" }}>
                  {insightsError}
                </div>
              )}
              {narrative && (
                <div className="card spacer" style={{ whiteSpace: "pre-wrap" }}>
                  {narrative}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </main>
  );
}
