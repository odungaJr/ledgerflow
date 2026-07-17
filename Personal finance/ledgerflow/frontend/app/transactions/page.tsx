"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  deleteTransaction,
  getAccounts,
  getCategories,
  getTransactions,
  importCsv,
  patchTransaction,
} from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import type { Account, Category, ImportResult, Transaction } from "@/lib/types";

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [accountFilter, setAccountFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [importAccountId, setImportAccountId] = useState("");
  const [importFile, setImportFile] = useState<File | null>(null);
  const [autoCategorise, setAutoCategorise] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  function loadTransactions() {
    getTransactions(accountFilter ? { account_id: accountFilter } : undefined)
      .then((data) => {
        setTransactions(data);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load transactions"))
      .finally(() => setLoading(false));
  }

  useEffect(loadTransactions, [accountFilter]);

  useEffect(() => {
    getAccounts().then((accs) => {
      setAccounts(accs);
      if (accs.length > 0) setImportAccountId((prev) => prev || accs[0].id);
    });
    getCategories().then(setCategories).catch(() => {});
  }, []);

  async function handleImport(e: FormEvent) {
    e.preventDefault();
    if (!importAccountId || !importFile) {
      setImportError("Choose an account and a CSV file.");
      return;
    }
    setImporting(true);
    setImportError(null);
    setImportResult(null);
    try {
      const result = await importCsv(importAccountId, importFile, autoCategorise);
      setImportResult(result);
      setImportFile(null);
      loadTransactions();
    } catch (e) {
      setImportError(e instanceof ApiError ? e.message : "Import failed");
    } finally {
      setImporting(false);
    }
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    setImportFile(e.target.files?.[0] ?? null);
  }

  async function handleCategorise(txn: Transaction, categoryName: string) {
    await patchTransaction(txn.id, { category_name: categoryName, is_confirmed: true });
    loadTransactions();
  }

  async function handleConfirm(txn: Transaction) {
    await patchTransaction(txn.id, { is_confirmed: true });
    loadTransactions();
  }

  async function handleDelete(txn: Transaction) {
    if (!confirm(`Delete transaction "${txn.description}"?`)) return;
    await deleteTransaction(txn.id);
    loadTransactions();
  }

  return (
    <main className="page">
      <div className="container">
        <div className="pageHeader">
          <h1>Transactions</h1>
        </div>

        <form className="form" onSubmit={handleImport}>
          <h2 className="sectionTitle">Import a bank statement</h2>
          <div className="formInline">
            <div className="formRow">
              <label htmlFor="import-account">Account</label>
              {accounts.length > 0 ? (
                <select
                  id="import-account"
                  value={importAccountId}
                  onChange={(e) => setImportAccountId(e.target.value)}
                >
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name} ({a.bank})
                    </option>
                  ))}
                </select>
              ) : (
                <span className="badge neutral">Add an account first</span>
              )}
            </div>
            <div className="formRow">
              <label htmlFor="import-file">CSV file</label>
              <input id="import-file" type="file" accept=".csv" onChange={handleFileChange} />
            </div>
            <button className="btn" type="submit" disabled={importing || accounts.length === 0}>
              {importing ? "Importing…" : "Import CSV"}
            </button>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <input
              id="auto-categorise"
              type="checkbox"
              style={{ width: "auto" }}
              checked={autoCategorise}
              onChange={(e) => setAutoCategorise(e.target.checked)}
            />
            <label htmlFor="auto-categorise" style={{ cursor: "pointer" }}>
              Auto-categorise with AI
            </label>
          </div>

          {importError && <div className="alert error">{importError}</div>}
          {importResult && (
            <div className="alert info">
              Imported {importResult.inserted} transaction{importResult.inserted === 1 ? "" : "s"}
              {importResult.skipped > 0 ? ` (${importResult.skipped} duplicate skipped)` : ""}.{" "}
              {importResult.categorised
                ? "AI categorisation ran."
                : "AI categorisation didn't run — categorise manually below."}
            </div>
          )}
        </form>

        <div className="spacer" style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "center" }}>
          <div className="formRow" style={{ maxWidth: "260px" }}>
            <label htmlFor="filter-account">Filter by account</label>
            <select
              id="filter-account"
              value={accountFilter}
              onChange={(e) => setAccountFilter(e.target.value)}
            >
              <option value="">All accounts</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="spacer">
          {loading && <p>Loading…</p>}
          {error && <div className="alert error">{error}</div>}
          {!loading && !error && transactions.length === 0 && (
            <div className="empty">No transactions yet — import a CSV statement above.</div>
          )}
          {!loading && transactions.length > 0 && (
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Description</th>
                    <th>Amount</th>
                    <th>Category</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((txn) => (
                    <tr key={txn.id}>
                      <td data-label="Date">{formatDate(txn.date)}</td>
                      <td data-label="Description">{txn.description}</td>
                      <td data-label="Amount">
                        <span style={{ color: txn.type === "credit" ? "var(--success)" : "var(--danger)" }}>
                          {txn.type === "credit" ? "+" : "-"}
                          {formatMoney(txn.amount)}
                        </span>
                      </td>
                      <td data-label="Category">
                        {categories.length > 0 ? (
                          <select
                            value={txn.category ?? ""}
                            onChange={(e) => handleCategorise(txn, e.target.value)}
                          >
                            <option value="" disabled>
                              Uncategorised
                            </option>
                            {categories.map((c) => (
                              <option key={c.id} value={c.name}>
                                {c.icon} {c.name}
                              </option>
                            ))}
                          </select>
                        ) : (
                          txn.category ?? "—"
                        )}
                      </td>
                      <td data-label="Status">
                        <span className={`badge ${txn.is_confirmed ? "ok" : "neutral"}`}>
                          {txn.is_confirmed ? "Confirmed" : "Pending"}
                        </span>
                      </td>
                      <td data-label="Actions">
                        <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", justifyContent: "flex-end" }}>
                          {!txn.is_confirmed && (
                            <button className="btn btnSecondary btnSmall" onClick={() => handleConfirm(txn)}>
                              Confirm
                            </button>
                          )}
                          <button className="btn btnDanger btnSmall" onClick={() => handleDelete(txn)}>
                            Delete
                          </button>
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
