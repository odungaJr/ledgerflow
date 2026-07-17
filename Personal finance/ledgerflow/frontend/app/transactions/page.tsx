"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useState } from "react";
import {
  ApiError,
  deleteTransaction,
  getAccounts,
  getCategories,
  getTransactions,
  importStatement,
  patchTransaction,
} from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import type { Account, Category, ImportResult, Transaction } from "@/lib/types";

const PAGE_SIZE = 50;

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [accountFilter, setAccountFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [search, setSearch] = useState("");

  const [importAccountId, setImportAccountId] = useState("");
  const [importFile, setImportFile] = useState<File | null>(null);
  const [autoCategorise, setAutoCategorise] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  const loadTransactions = useCallback(() => {
    getTransactions({
      account_id: accountFilter || undefined,
      category: categoryFilter || undefined,
      txn_type: typeFilter || undefined,
      from_date: fromDate || undefined,
      to_date: toDate || undefined,
      search: search || undefined,
      limit: PAGE_SIZE,
      offset: 0,
    })
      .then((data) => {
        setTransactions(data);
        setHasMore(data.length === PAGE_SIZE);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load transactions"))
      .finally(() => setLoading(false));
  }, [accountFilter, categoryFilter, typeFilter, fromDate, toDate, search]);

  useEffect(() => {
    loadTransactions();
  }, [loadTransactions]);

  useEffect(() => {
    getAccounts().then((accs) => {
      setAccounts(accs);
      if (accs.length > 0) setImportAccountId((prev) => prev || accs[0].id);
    });
    getCategories().then(setCategories).catch(() => {});
  }, []);

  async function handleLoadMore() {
    setLoadingMore(true);
    try {
      const more = await getTransactions({
        account_id: accountFilter || undefined,
        category: categoryFilter || undefined,
        txn_type: typeFilter || undefined,
        from_date: fromDate || undefined,
        to_date: toDate || undefined,
        search: search || undefined,
        limit: PAGE_SIZE,
        offset: transactions.length,
      });
      setTransactions((prev) => [...prev, ...more]);
      setHasMore(more.length === PAGE_SIZE);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load more transactions");
    } finally {
      setLoadingMore(false);
    }
  }

  async function handleImport(e: FormEvent) {
    e.preventDefault();
    if (!importAccountId || !importFile) {
      setImportError("Choose an account and a CSV or PDF file.");
      return;
    }
    const fileType = importFile.name.toLowerCase().endsWith(".pdf") ? "pdf" : "csv";
    setImporting(true);
    setImportError(null);
    setImportResult(null);
    try {
      const result = await importStatement(importAccountId, importFile, fileType, autoCategorise);
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

  async function handleNotesBlur(txn: Transaction, value: string) {
    if (value === (txn.notes ?? "")) return;
    await patchTransaction(txn.id, { notes: value });
  }

  async function handleDelete(txn: Transaction) {
    if (!confirm(`Delete transaction "${txn.description}"?`)) return;
    await deleteTransaction(txn.id);
    loadTransactions();
  }

  function clearFilters() {
    setAccountFilter("");
    setCategoryFilter("");
    setTypeFilter("");
    setFromDate("");
    setToDate("");
    setSearch("");
  }

  const filtersActive =
    accountFilter || categoryFilter || typeFilter || fromDate || toDate || search;

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
              <label htmlFor="import-file">Statement file (CSV or PDF)</label>
              <input id="import-file" type="file" accept=".csv,.pdf" onChange={handleFileChange} />
            </div>
            <button className="btn" type="submit" disabled={importing || accounts.length === 0}>
              {importing ? "Importing…" : "Import statement"}
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

        <div className="spacer">
          <h2 className="sectionTitle">Filters</h2>
          <div className="formInline">
            <div className="formRow">
              <label htmlFor="filter-search">Search description</label>
              <input
                id="filter-search"
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="e.g. supermarket"
              />
            </div>
            <div className="formRow">
              <label htmlFor="filter-account">Account</label>
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
            <div className="formRow">
              <label htmlFor="filter-category">Category</label>
              <select
                id="filter-category"
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
              >
                <option value="">All categories</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.name}>
                    {c.icon} {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="formRow" style={{ maxWidth: "130px" }}>
              <label htmlFor="filter-type">Type</label>
              <select id="filter-type" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
                <option value="">All</option>
                <option value="debit">Debit</option>
                <option value="credit">Credit</option>
              </select>
            </div>
            <div className="formRow" style={{ maxWidth: "160px" }}>
              <label htmlFor="filter-from">From date</label>
              <input
                id="filter-from"
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
              />
            </div>
            <div className="formRow" style={{ maxWidth: "160px" }}>
              <label htmlFor="filter-to">To date</label>
              <input id="filter-to" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
            </div>
            {filtersActive && (
              <button type="button" className="btn btnSecondary" onClick={clearFilters}>
                Clear filters
              </button>
            )}
          </div>
        </div>

        <div className="spacer">
          {loading && <p>Loading…</p>}
          {error && <div className="alert error">{error}</div>}
          {!loading && !error && transactions.length === 0 && (
            <div className="empty">
              {filtersActive
                ? "No transactions match these filters."
                : "No transactions yet — import a CSV or PDF statement above."}
            </div>
          )}
          {!loading && transactions.length > 0 && (
            <>
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Description</th>
                      <th>Amount</th>
                      <th>Category</th>
                      <th>Notes</th>
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
                        <td data-label="Notes">
                          <input
                            key={txn.id}
                            defaultValue={txn.notes ?? ""}
                            placeholder="Add a note…"
                            onBlur={(e) => handleNotesBlur(txn, e.target.value)}
                          />
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

              {hasMore && (
                <div style={{ textAlign: "center", marginTop: "1rem" }}>
                  <button className="btn btnSecondary" onClick={handleLoadMore} disabled={loadingMore}>
                    {loadingMore ? "Loading…" : "Load more"}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </main>
  );
}
