"use client";

import { FormEvent, useEffect, useState } from "react";
import { ApiError, createAccount, deleteAccount, getAccounts, updateAccount } from "@/lib/api";
import { todayIso } from "@/lib/date";
import { formatDate, formatMoney } from "@/lib/format";
import type { Account } from "@/lib/types";

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [bank, setBank] = useState("");
  const [currency, setCurrency] = useState("TZS");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editBank, setEditBank] = useState("");

  const [balanceEditingId, setBalanceEditingId] = useState<string | null>(null);
  const [balanceAmount, setBalanceAmount] = useState("");
  const [balanceDate, setBalanceDate] = useState(todayIso());

  function load() {
    getAccounts(includeInactive)
      .then((data) => {
        setAccounts(data);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load accounts"))
      .finally(() => setLoading(false));
  }

  useEffect(load, [includeInactive]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      await createAccount({ name, bank, currency: currency || "TZS" });
      setName("");
      setBank("");
      setCurrency("TZS");
      load();
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Failed to create account");
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleActive(account: Account) {
    await updateAccount(account.id, { is_active: !account.is_active });
    load();
  }

  function startEdit(account: Account) {
    setEditingId(account.id);
    setEditName(account.name);
    setEditBank(account.bank);
  }

  async function saveEdit(id: string) {
    await updateAccount(id, { name: editName, bank: editBank });
    setEditingId(null);
    load();
  }

  async function handleDelete(account: Account) {
    if (!confirm(`Delete "${account.name}"? This also deletes all its transactions.`)) return;
    await deleteAccount(account.id);
    load();
  }

  function startBalanceEdit(account: Account) {
    setBalanceEditingId(account.id);
    setBalanceAmount(account.current_balance != null ? String(account.current_balance) : "");
    setBalanceDate(todayIso());
  }

  async function saveBalance(id: string) {
    const amount = Number(balanceAmount);
    if (Number.isNaN(amount)) return;
    await updateAccount(id, { manual_balance: amount, manual_balance_date: balanceDate });
    setBalanceEditingId(null);
    load();
  }

  return (
    <main className="page">
      <div className="container">
        <div className="pageHeader">
          <h1>Accounts</h1>
        </div>

        <form className="form" onSubmit={handleCreate}>
          <h2 className="sectionTitle">Add an account</h2>
          <div className="formInline">
            <div className="formRow">
              <label htmlFor="acc-name">Name</label>
              <input
                id="acc-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. CRDB Salary Account"
                required
              />
            </div>
            <div className="formRow">
              <label htmlFor="acc-bank">Bank</label>
              <input
                id="acc-bank"
                value={bank}
                onChange={(e) => setBank(e.target.value)}
                placeholder="e.g. CRDB"
                required
              />
            </div>
            <div className="formRow" style={{ maxWidth: "100px" }}>
              <label htmlFor="acc-currency">Currency</label>
              <input
                id="acc-currency"
                value={currency}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                maxLength={10}
              />
            </div>
            <button className="btn" type="submit" disabled={submitting}>
              {submitting ? "Adding…" : "Add account"}
            </button>
          </div>
          {formError && <div className="alert error">{formError}</div>}
        </form>

        <div className="spacer" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <input
            id="include-inactive"
            type="checkbox"
            style={{ width: "auto" }}
            checked={includeInactive}
            onChange={(e) => setIncludeInactive(e.target.checked)}
          />
          <label htmlFor="include-inactive" style={{ cursor: "pointer" }}>
            Show inactive accounts
          </label>
        </div>

        <div className="spacer">
          {loading && <p>Loading…</p>}
          {error && <div className="alert error">{error}</div>}
          {!loading && !error && accounts.length === 0 && (
            <div className="empty">No accounts yet — add one above to start importing transactions.</div>
          )}
          {!loading && accounts.length > 0 && (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Bank</th>
                    <th>Currency</th>
                    <th>Balance</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((account) => (
                    <tr key={account.id}>
                      <td data-label="Name">
                        {editingId === account.id ? (
                          <input value={editName} onChange={(e) => setEditName(e.target.value)} />
                        ) : (
                          account.name
                        )}
                      </td>
                      <td data-label="Bank">
                        {editingId === account.id ? (
                          <input value={editBank} onChange={(e) => setEditBank(e.target.value)} />
                        ) : (
                          account.bank
                        )}
                      </td>
                      <td data-label="Currency">{account.currency}</td>
                      <td data-label="Balance">
                        {balanceEditingId === account.id ? (
                          <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                            <input
                              type="number"
                              step="0.01"
                              value={balanceAmount}
                              onChange={(e) => setBalanceAmount(e.target.value)}
                              style={{ maxWidth: "140px" }}
                              placeholder="Amount"
                            />
                            <input
                              type="date"
                              value={balanceDate}
                              onChange={(e) => setBalanceDate(e.target.value)}
                              style={{ maxWidth: "160px" }}
                            />
                            <button className="btn btnSmall" onClick={() => saveBalance(account.id)}>
                              Save
                            </button>
                            <button
                              className="btn btnSecondary btnSmall"
                              onClick={() => setBalanceEditingId(null)}
                            >
                              Cancel
                            </button>
                          </div>
                        ) : account.current_balance != null ? (
                          <>
                            {formatMoney(account.current_balance, account.currency)}
                            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                              {account.balance_source === "manual" ? "manual" : "from transactions"}
                              {account.balance_as_of && `, as of ${formatDate(account.balance_as_of)}`}
                            </div>
                          </>
                        ) : (
                          <span style={{ color: "var(--text-muted)" }}>—</span>
                        )}
                      </td>
                      <td data-label="Status">
                        <span className={`badge ${account.is_active ? "ok" : "neutral"}`}>
                          {account.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td data-label="Created">{formatDate(account.created_at)}</td>
                      <td data-label="Actions">
                        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", justifyContent: "flex-end" }}>
                          {editingId === account.id ? (
                            <>
                              <button className="btn btnSmall" onClick={() => saveEdit(account.id)}>
                                Save
                              </button>
                              <button
                                className="btn btnSecondary btnSmall"
                                onClick={() => setEditingId(null)}
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                className="btn btnSecondary btnSmall"
                                onClick={() => startEdit(account)}
                              >
                                Edit
                              </button>
                              <button
                                className="btn btnSecondary btnSmall"
                                onClick={() => startBalanceEdit(account)}
                              >
                                Set balance
                              </button>
                              <button
                                className="btn btnSecondary btnSmall"
                                onClick={() => toggleActive(account)}
                              >
                                {account.is_active ? "Deactivate" : "Activate"}
                              </button>
                              <button
                                className="btn btnDanger btnSmall"
                                onClick={() => handleDelete(account)}
                              >
                                Delete
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
