"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Sparkline from "@/components/Sparkline";
import IncomeExpenseChart from "@/components/charts/IncomeExpenseChart";
import CategoryBarChart from "@/components/charts/CategoryBarChart";
import CategoryPieChart from "@/components/charts/CategoryPieChart";
import { ApiError, getDashboardInsights, getDashboardSummary, getIncomeEntries, getTransactions } from "@/lib/api";
import { dateToIso, todayIso } from "@/lib/date";
import { formatMoney } from "@/lib/format";
import type { DashboardSummaryResponse } from "@/lib/types";

function formatTypeLabel(assetType: string): string {
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

  // Default to the latest bank transaction's month — that's the dominant,
  // most data-rich section of the dashboard (income/expenses, top
  // categories, budget alerts all depend on it). Only fall back to income
  // data when there are no transactions at all yet.
  //
  // Deliberately NOT "whichever is more recent, transactions or income":
  // recurring income entries get auto-generated ahead of when they're due
  // whenever you preview a future month (e.g. clicking the period arrows
  // forward on the Income page) — those future-dated rows would otherwise
  // pull the dashboard's default past every transaction that exists,
  // landing on a period with no transactions at all. Income candidates are
  // also capped at today for the same reason.
  useEffect(() => {
    Promise.all([
      getTransactions({ limit: 1 }).catch(() => []),
      getIncomeEntries().catch(() => []),
    ]).then(([txns, income]) => {
      let ref: Date;
      if (txns.length > 0) {
        ref = new Date(txns[0].date);
      } else {
        const today = todayIso();
        const dueIncomeDates = income.map((i) => i.expected_date).filter((d) => d <= today);
        ref = dueIncomeDates.length > 0
          ? new Date(dueIncomeDates.reduce((latest, d) => (d > latest ? d : latest)))
          : new Date();
      }
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

            <div className="spacer">
              <h2 className="sectionTitle">Income vs expenses</h2>
              <div className="card">
                <IncomeExpenseChart data={data.monthly_trend} currency={currency} />
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
              <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))" }}>
                <div className="card">
                  <p className="statLabel" style={{ marginBottom: "0.75rem" }}>
                    Share of spending
                  </p>
                  <CategoryPieChart
                    data={data.summary.top_categories}
                    currency={currency}
                    onSelect={(name) => {
                      const url = categoryDrilldownUrl(name);
                      if (url) router.push(url);
                    }}
                  />
                </div>
                <div className="card">
                  <p className="statLabel" style={{ marginBottom: "0.75rem" }}>
                    Spend vs. budget
                  </p>
                  <CategoryBarChart
                    data={data.summary.top_categories}
                    currency={currency}
                    onSelect={(name) => {
                      const url = categoryDrilldownUrl(name);
                      if (url) router.push(url);
                    }}
                  />
                </div>
              </div>
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
                  <p className="statValue positive">{formatMoney(data.assets.total_value)}</p>
                </div>
                <div className="card">
                  <p className="statLabel">Total liabilities</p>
                  <p className="statValue negative">{formatMoney(data.liabilities.total_value)}</p>
                </div>
                <div className="card">
                  <p className="statLabel">Net worth</p>
                  <p className={`statValue ${data.net_worth.total >= 0 ? "positive" : "negative"}`}>
                    {formatMoney(data.net_worth.total)}
                  </p>
                </div>
              </div>

              <div className="card spacer">
                <p className="statLabel">Net worth trend</p>
                <Sparkline data={data.net_worth.trend.map((t) => ({ date: t.date, total_value: t.net_worth }))} />
              </div>

              <div className="grid spacer" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
                <div>
                  <p className="statLabel" style={{ marginBottom: "0.5rem" }}>
                    Assets by type
                  </p>
                  {data.assets.breakdown.length > 0 ? (
                    <div className="tableWrap">
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
                              <td data-label="Type">{formatTypeLabel(row.asset_type)}</td>
                              <td data-label="Value">{formatMoney(row.total)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="empty">No assets tracked yet.</div>
                  )}
                  <p style={{ marginTop: "0.6rem", fontSize: "0.85rem" }}>
                    <Link href="/assets">Manage assets →</Link>
                  </p>
                </div>

                <div>
                  <p className="statLabel" style={{ marginBottom: "0.5rem" }}>
                    Liabilities by type
                  </p>
                  {data.liabilities.breakdown.length > 0 ? (
                    <div className="tableWrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Type</th>
                            <th>Owed</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.liabilities.breakdown.map((row) => (
                            <tr
                              key={row.liability_type}
                              onClick={() => router.push("/liabilities")}
                              style={{ cursor: "pointer" }}
                            >
                              <td data-label="Type">{formatTypeLabel(row.liability_type)}</td>
                              <td data-label="Owed">{formatMoney(row.total)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="empty">No liabilities tracked yet.</div>
                  )}
                  <p style={{ marginTop: "0.6rem", fontSize: "0.85rem" }}>
                    <Link href="/liabilities">Manage liabilities →</Link>
                  </p>
                </div>
              </div>
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
