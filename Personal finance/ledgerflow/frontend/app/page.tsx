"use client";

import { useEffect, useState } from "react";
import { ApiError, getDashboardInsights, getDashboardSummary } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { DashboardSummaryResponse } from "@/lib/types";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardSummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [narrative, setNarrative] = useState<string | null>(null);
  const [insightsError, setInsightsError] = useState<string | null>(null);
  const [insightsLoading, setInsightsLoading] = useState(false);

  useEffect(() => {
    getDashboardSummary()
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load dashboard"))
      .finally(() => setLoading(false));
  }, []);

  async function handleGenerateInsights() {
    setInsightsLoading(true);
    setInsightsError(null);
    try {
      const res = await getDashboardInsights();
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

  return (
    <main className="page">
      <div className="container">
        <div className="pageHeader">
          <h1>Dashboard</h1>
          {data && <span className="badge neutral">{data.summary.period}</span>}
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
                  {data.budget_alerts.map((b) => (
                    <div className="card" key={b.budget_id}>
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
                    </div>
                  ))}
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
                        <tr key={c.name}>
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
