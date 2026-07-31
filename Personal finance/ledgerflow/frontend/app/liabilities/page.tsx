"use client";

import { FormEvent, useEffect, useState } from "react";
import { addLiabilityValue, ApiError, createLiability, deleteLiability, getLiabilities } from "@/lib/api";
import { todayIso } from "@/lib/date";
import { formatDate, formatMoney } from "@/lib/format";
import type { Liability } from "@/lib/types";

const LIABILITY_TYPES: { value: Liability["liability_type"]; label: string }[] = [
  { value: "credit_card", label: "Credit Card" },
  { value: "loan", label: "Loan" },
  { value: "mortgage", label: "Mortgage" },
  { value: "personal_debt", label: "Personal Debt" },
  { value: "other", label: "Other" },
];

export default function LiabilitiesPage() {
  const [liabilities, setLiabilities] = useState<Liability[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [liabilityType, setLiabilityType] = useState<Liability["liability_type"]>("loan");
  const [totalValue, setTotalValue] = useState("");
  const [currency, setCurrency] = useState("TZS");
  const [valueDate, setValueDate] = useState(todayIso());
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [updateValue, setUpdateValue] = useState("");
  const [updateDate, setUpdateDate] = useState(todayIso());

  function load() {
    setLoading(true);
    getLiabilities()
      .then((data) => {
        setLiabilities(data);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load liabilities"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    const total = Number(totalValue);
    if (!name.trim() || !total || total <= 0) {
      setFormError("Enter a name and a balance owed greater than zero.");
      return;
    }
    setSubmitting(true);
    try {
      await createLiability({
        name: name.trim(),
        liability_type: liabilityType,
        currency,
        value_date: valueDate,
        total_value: total,
      });
      setName("");
      setTotalValue("");
      load();
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Failed to create liability");
    } finally {
      setSubmitting(false);
    }
  }

  function startUpdate(liability: Liability) {
    setUpdatingId(liability.id);
    setUpdateValue(String(liability.current_value ?? ""));
    setUpdateDate(todayIso());
  }

  async function saveUpdate(id: string) {
    const value = Number(updateValue);
    if (!value || value <= 0) return;
    await addLiabilityValue(id, { value_date: updateDate, total_value: value });
    setUpdatingId(null);
    load();
  }

  async function handleDelete(liability: Liability) {
    if (!confirm(`Delete "${liability.name}"? This removes its full balance history.`)) return;
    await deleteLiability(liability.id);
    load();
  }

  const totalOwed = liabilities.reduce((sum, l) => sum + (l.current_value ?? 0), 0);

  return (
    <main className="page">
      <div className="container">
        <div className="pageHeader">
          <h1>Liabilities</h1>
          <span className="badge neutral">Total owed: {formatMoney(totalOwed)}</span>
        </div>

        <form className="form" onSubmit={handleCreate}>
          <h2 className="sectionTitle">Add a liability</h2>
          <div className="formInline">
            <div className="formRow">
              <label htmlFor="liability-name">Name</label>
              <input
                id="liability-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="NMB Car Loan"
                required
              />
            </div>
            <div className="formRow" style={{ maxWidth: "160px" }}>
              <label htmlFor="liability-type">Type</label>
              <select
                id="liability-type"
                value={liabilityType}
                onChange={(e) => setLiabilityType(e.target.value as Liability["liability_type"])}
              >
                {LIABILITY_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="formRow" style={{ maxWidth: "160px" }}>
              <label htmlFor="liability-total-value">Balance owed</label>
              <input
                id="liability-total-value"
                type="number"
                min="1"
                step="0.01"
                value={totalValue}
                onChange={(e) => setTotalValue(e.target.value)}
                placeholder="1000000"
                required
              />
            </div>
            <div className="formRow" style={{ maxWidth: "160px" }}>
              <label htmlFor="liability-date">As of</label>
              <input id="liability-date" type="date" value={valueDate} onChange={(e) => setValueDate(e.target.value)} />
            </div>
            <button className="btn" type="submit" disabled={submitting}>
              {submitting ? "Adding…" : "Add liability"}
            </button>
          </div>
          {formError && <div className="alert error">{formError}</div>}
        </form>

        <div className="spacer">
          {loading && <p>Loading…</p>}
          {error && <div className="alert error">{error}</div>}
          {!loading && !error && liabilities.length === 0 && (
            <div className="empty">No liabilities tracked yet — add a loan, credit card, or other debt above.</div>
          )}
          {!loading && liabilities.length > 0 && (
            <div className="grid">
              {liabilities.map((liability) => {
                const change = liability.change_amount ?? 0;
                return (
                  <div className="card" key={liability.id}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                      <p className="statLabel" style={{ margin: 0 }}>
                        {liability.name}
                      </p>
                      <span className="badge neutral">
                        {LIABILITY_TYPES.find((t) => t.value === liability.liability_type)?.label}
                      </span>
                    </div>

                    {/* For debts, a shrinking balance is the good direction — invert the usual positive/negative coloring. */}
                    <p className={`statValue ${change <= 0 ? "positive" : "negative"}`} style={{ marginTop: "0.4rem" }}>
                      {formatMoney(liability.current_value ?? 0, liability.currency)}
                    </p>
                    <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                      {[
                        change !== 0 && `${change > 0 ? "+" : ""}${formatMoney(change, liability.currency)} since first entry`,
                        liability.value_date && `as of ${formatDate(liability.value_date)}`,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>

                    {updatingId === liability.id ? (
                      <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.6rem", flexWrap: "wrap" }}>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          value={updateValue}
                          onChange={(e) => setUpdateValue(e.target.value)}
                          style={{ maxWidth: "140px" }}
                        />
                        <input
                          type="date"
                          value={updateDate}
                          onChange={(e) => setUpdateDate(e.target.value)}
                          style={{ maxWidth: "160px" }}
                        />
                        <button className="btn btnSmall" onClick={() => saveUpdate(liability.id)}>
                          Save
                        </button>
                        <button className="btn btnSecondary btnSmall" onClick={() => setUpdatingId(null)}>
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.75rem" }}>
                        <button className="btn btnSecondary btnSmall" onClick={() => startUpdate(liability)}>
                          Update balance
                        </button>
                        <button className="btn btnDanger btnSmall" onClick={() => handleDelete(liability)}>
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
