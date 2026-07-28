"use client";

import { FormEvent, useEffect, useState } from "react";
import { ApiError, createBudget, deleteBudget, getBudgets, getCategories, updateBudget } from "@/lib/api";
import { todayIso } from "@/lib/date";
import { formatMoney } from "@/lib/format";
import type { BudgetStatus, Category } from "@/lib/types";

export default function BudgetsPage() {
  const [budgets, setBudgets] = useState<BudgetStatus[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [categoryName, setCategoryName] = useState("");
  const [limitAmount, setLimitAmount] = useState("");
  const [period, setPeriod] = useState<"monthly" | "weekly">("monthly");
  const [startDate, setStartDate] = useState(todayIso());
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editLimit, setEditLimit] = useState("");

  function load() {
    getBudgets()
      .then((data) => {
        setBudgets(data);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load budgets"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
    getCategories()
      .then((cats) => {
        setCategories(cats);
        if (cats.length > 0) setCategoryName((prev) => prev || cats[0].name);
      })
      .catch(() => {
        // Categories are a convenience for the dropdown — budget list still works without them.
      });
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    const amount = Number(limitAmount);
    if (!categoryName || !amount || amount <= 0) {
      setFormError("Pick a category and enter a limit greater than zero.");
      return;
    }
    setSubmitting(true);
    try {
      await createBudget({ category_name: categoryName, limit_amount: amount, period, start_date: startDate });
      setLimitAmount("");
      load();
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Failed to create budget");
    } finally {
      setSubmitting(false);
    }
  }

  function startEdit(budget: BudgetStatus) {
    setEditingId(budget.budget_id);
    setEditLimit(String(budget.limit));
  }

  async function saveEdit(id: string) {
    const amount = Number(editLimit);
    if (!amount || amount <= 0) return;
    await updateBudget(id, { limit_amount: amount });
    setEditingId(null);
    load();
  }

  async function handleDelete(budget: BudgetStatus) {
    if (!confirm(`Delete the ${budget.category_name} budget?`)) return;
    await deleteBudget(budget.budget_id);
    load();
  }

  return (
    <main className="page">
      <div className="container">
        <div className="pageHeader">
          <h1>Budgets</h1>
        </div>

        <form className="form" onSubmit={handleCreate}>
          <h2 className="sectionTitle">Add a budget</h2>
          <div className="formInline">
            <div className="formRow">
              <label htmlFor="budget-category">Category</label>
              {categories.length > 0 ? (
                <select
                  id="budget-category"
                  value={categoryName}
                  onChange={(e) => setCategoryName(e.target.value)}
                >
                  {categories.map((c) => (
                    <option key={c.id} value={c.name}>
                      {c.icon} {c.name}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id="budget-category"
                  value={categoryName}
                  onChange={(e) => setCategoryName(e.target.value)}
                  placeholder="Category name"
                />
              )}
            </div>
            <div className="formRow">
              <label htmlFor="budget-limit">Limit</label>
              <input
                id="budget-limit"
                type="number"
                min="1"
                step="0.01"
                value={limitAmount}
                onChange={(e) => setLimitAmount(e.target.value)}
                placeholder="100000"
                required
              />
            </div>
            <div className="formRow" style={{ maxWidth: "140px" }}>
              <label htmlFor="budget-period">Period</label>
              <select
                id="budget-period"
                value={period}
                onChange={(e) => setPeriod(e.target.value as "monthly" | "weekly")}
              >
                <option value="monthly">Monthly</option>
                <option value="weekly">Weekly</option>
              </select>
            </div>
            <div className="formRow" style={{ maxWidth: "160px" }}>
              <label htmlFor="budget-start">Start date</label>
              <input
                id="budget-start"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <button className="btn" type="submit" disabled={submitting}>
              {submitting ? "Adding…" : "Add budget"}
            </button>
          </div>
          {formError && <div className="alert error">{formError}</div>}
        </form>

        <div className="spacer">
          {loading && <p>Loading…</p>}
          {error && <div className="alert error">{error}</div>}
          {!loading && !error && budgets.length === 0 && (
            <div className="empty">No budgets yet — add one above to start tracking spending limits.</div>
          )}
          {!loading && budgets.length > 0 && (
            <div className="grid">
              {budgets.map((b) => {
                const state = b.is_breached ? "danger" : b.is_warning ? "warning" : "ok";
                return (
                  <div className="card" key={b.budget_id}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <p className="statLabel" style={{ margin: 0 }}>
                        {b.category_name} · {b.period}
                      </p>
                      <span className={`badge ${state}`}>
                        {b.is_breached ? "Over" : b.is_warning ? "Near limit" : "On track"}
                      </span>
                    </div>

                    <div className="spacer" style={{ marginTop: "0.6rem" }}>
                      <div className="progress">
                        <div
                          className={`progressFill ${state === "ok" ? "" : state}`}
                          style={{ width: `${Math.min(b.pct_used * 100, 100)}%` }}
                        />
                      </div>
                    </div>

                    {editingId === b.budget_id ? (
                      <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.6rem" }}>
                        <input
                          type="number"
                          min="1"
                          step="0.01"
                          value={editLimit}
                          onChange={(e) => setEditLimit(e.target.value)}
                        />
                        <button className="btn btnSmall" onClick={() => saveEdit(b.budget_id)}>
                          Save
                        </button>
                        <button className="btn btnSecondary btnSmall" onClick={() => setEditingId(null)}>
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <p style={{ marginTop: "0.5rem", fontSize: "0.85rem", color: "var(--text-muted)" }}>
                        {formatMoney(b.spent)} of {formatMoney(b.limit)} ({formatMoney(b.remaining)} left)
                      </p>
                    )}

                    {editingId !== b.budget_id && (
                      <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.75rem" }}>
                        <button className="btn btnSecondary btnSmall" onClick={() => startEdit(b)}>
                          Edit limit
                        </button>
                        <button className="btn btnDanger btnSmall" onClick={() => handleDelete(b)}>
                          Delete
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
