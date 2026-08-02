"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  ApiError,
  bulkPatchTransactions,
  categorisePendingTransactions,
  deleteAllTransactions,
  deleteTransaction,
  getAccounts,
  getCategories,
  getTransactions,
  importStatement,
  patchTransaction,
} from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import type { Account, Category, CategorisePendingResult, Transaction } from "@/lib/types";

const PAGE_SIZE = 50;

type ImportFileOutcome = {
  name: string;
  status: "success" | "duplicate" | "error";
  detail: string;
};

function accountLabel(accounts: Account[], accountId: string): string {
  return accounts.find((a) => a.id === accountId)?.name ?? "—";
}

export default function TransactionsPage() {
  const searchParams = useSearchParams();

  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [accountFilter, setAccountFilter] = useState(() => searchParams.get("account_id") ?? "");
  const [categoryFilter, setCategoryFilter] = useState(() => searchParams.get("category") ?? "");
  const [typeFilter, setTypeFilter] = useState(() => searchParams.get("type") ?? "");
  const [fromDate, setFromDate] = useState(() => searchParams.get("from_date") ?? "");
  const [toDate, setToDate] = useState(() => searchParams.get("to_date") ?? "");
  const [search, setSearch] = useState(() => searchParams.get("search") ?? "");

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkCategory, setBulkCategory] = useState("");
  const [bulkApplying, setBulkApplying] = useState(false);
  const [clearingAll, setClearingAll] = useState(false);

  const [importAccountId, setImportAccountId] = useState("");
  const [importFiles, setImportFiles] = useState<File[]>([]);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [autoCategorise, setAutoCategorise] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importProgress, setImportProgress] = useState<{ completed: number; total: number } | null>(null);
  const [importFileResults, setImportFileResults] = useState<ImportFileOutcome[]>([]);

  const [categorising, setCategorising] = useState(false);
  const [categoriseError, setCategoriseError] = useState<string | null>(null);
  const [categoriseResult, setCategoriseResult] = useState<CategorisePendingResult | null>(null);

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
    setSelectedIds(new Set());
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
    if (!importAccountId || importFiles.length === 0) {
      setImportError("Choose an account and at least one CSV or PDF file.");
      return;
    }
    setImporting(true);
    setImportError(null);
    setImportFileResults([]);
    setImportProgress({ completed: 0, total: importFiles.length });

    const results: ImportFileOutcome[] = [];
    for (const file of importFiles) {
      const fileType = file.name.toLowerCase().endsWith(".pdf") ? "pdf" : "csv";
      try {
        const result = await importStatement(importAccountId, file, fileType, autoCategorise);
        if (result.duplicate_statement) {
          results.push({ name: file.name, status: "duplicate", detail: "Already imported — skipped." });
        } else {
          const parts = [`${result.inserted} imported`];
          if (result.skipped > 0) {
            parts.push(`${result.skipped} duplicate row${result.skipped === 1 ? "" : "s"} skipped`);
          }
          if (autoCategorise) {
            parts.push(result.categorised ? "AI categorised" : "AI categorisation unavailable");
          }
          results.push({ name: file.name, status: "success", detail: parts.join(", ") });
        }
      } catch (err) {
        results.push({
          name: file.name,
          status: "error",
          detail: err instanceof ApiError ? err.message : "Import failed",
        });
      }
      // Update after each file so the progress bar and per-file list move
      // along live instead of jumping all at once at the end.
      setImportFileResults([...results]);
      setImportProgress((prev) => (prev ? { ...prev, completed: prev.completed + 1 } : prev));
    }

    setImportFiles([]);
    setFileInputKey((k) => k + 1);
    setImporting(false);
    loadTransactions();
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    setImportFiles(Array.from(e.target.files ?? []));
  }

  async function handleCategorisePending() {
    setCategorising(true);
    setCategoriseError(null);
    setCategoriseResult(null);
    try {
      const result = await categorisePendingTransactions();
      setCategoriseResult(result);
      loadTransactions();
    } catch (e) {
      setCategoriseError(e instanceof ApiError ? e.message : "Failed to run AI categorisation");
    } finally {
      setCategorising(false);
    }
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

  function toggleSelected(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    setSelectedIds((prev) =>
      prev.size === transactions.length ? new Set() : new Set(transactions.map((t) => t.id))
    );
  }

  async function handleBulkApply() {
    if (!bulkCategory || selectedIds.size === 0) return;
    setBulkApplying(true);
    try {
      await bulkPatchTransactions(Array.from(selectedIds), bulkCategory);
      setSelectedIds(new Set());
      setBulkCategory("");
      loadTransactions();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to apply category to selected transactions");
    } finally {
      setBulkApplying(false);
    }
  }

  function clearFilters() {
    setAccountFilter("");
    setCategoryFilter("");
    setTypeFilter("");
    setFromDate("");
    setToDate("");
    setSearch("");
  }

  async function handleClearAll() {
    if (!confirm("Delete ALL transactions across every account? This cannot be undone.")) return;
    if (prompt('Type "DELETE" to confirm permanently clearing all transactions:') !== "DELETE") return;
    setClearingAll(true);
    try {
      const result = await deleteAllTransactions();
      setSelectedIds(new Set());
      loadTransactions();
      alert(`Deleted ${result.deleted} transaction${result.deleted === 1 ? "" : "s"}.`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to clear transactions");
    } finally {
      setClearingAll(false);
    }
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
              <label htmlFor="import-file">Statement file(s) (CSV or PDF)</label>
              <input
                key={fileInputKey}
                id="import-file"
                type="file"
                accept=".csv,.pdf"
                multiple
                onChange={handleFileChange}
              />
              {importFiles.length > 0 && (
                <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  {importFiles.length} file{importFiles.length === 1 ? "" : "s"} selected
                </span>
              )}
            </div>
            <button className="btn" type="submit" disabled={importing || accounts.length === 0}>
              {importing ? "Importing…" : "Import statement(s)"}
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

          {importProgress && (
            <div style={{ marginTop: "0.75rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", marginBottom: "0.3rem" }}>
                <span>
                  {importing
                    ? `Importing ${importProgress.completed + 1} of ${importProgress.total}…`
                    : `Done — ${importProgress.completed} of ${importProgress.total} processed`}
                </span>
                <span>{Math.round((importProgress.completed / importProgress.total) * 100)}%</span>
              </div>
              <div style={{ height: "8px", borderRadius: "4px", background: "var(--border)", overflow: "hidden" }}>
                <div
                  style={{
                    height: "100%",
                    width: `${(importProgress.completed / importProgress.total) * 100}%`,
                    background: "var(--primary)",
                    transition: "width 0.2s ease",
                  }}
                />
              </div>
            </div>
          )}

          {importFileResults.length > 0 && (
            <ul style={{ listStyle: "none", padding: 0, marginTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              {importFileResults.map((r, i) => (
                <li key={`${r.name}-${i}`} style={{ fontSize: "0.85rem", display: "flex", gap: "0.5rem", alignItems: "baseline" }}>
                  <span
                    className={`badge ${r.status === "success" ? "ok" : r.status === "duplicate" ? "neutral" : "danger"}`}
                  >
                    {r.status === "success" ? "Imported" : r.status === "duplicate" ? "Duplicate" : "Failed"}
                  </span>
                  <span style={{ fontWeight: 600 }}>{r.name}</span>
                  <span style={{ color: "var(--text-muted)" }}>{r.detail}</span>
                </li>
              ))}
            </ul>
          )}
        </form>

        <div className="spacer card" style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
          <div style={{ flex: "1 1 260px" }}>
            <p className="statLabel">AI categorisation</p>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              Scan every uncategorised transaction across all accounts and let AI suggest a
              category (runs locally via Ollama — no data leaves this machine).
            </p>
          </div>
          <button className="btn" onClick={handleCategorisePending} disabled={categorising}>
            {categorising ? "Scanning…" : "Scan & categorise"}
          </button>
        </div>
        {categoriseError && <div className="alert error">{categoriseError}</div>}
        {categoriseResult && (
          <div className="alert info">
            {categoriseResult.scanned === 0
              ? "No uncategorised transactions found — everything's already categorised."
              : categoriseResult.ai_available
              ? `Categorised ${categoriseResult.categorised} of ${categoriseResult.scanned} uncategorised transaction${categoriseResult.scanned === 1 ? "" : "s"}.`
              : "AI categorisation isn't available right now (is Ollama running?) — try again shortly."}
          </div>
        )}

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
              {selectedIds.size > 0 && (
                <div
                  className="card"
                  style={{ display: "flex", alignItems: "center", gap: "0.6rem", flexWrap: "wrap", marginBottom: "0.75rem" }}
                >
                  <span>{selectedIds.size} selected</span>
                  <select value={bulkCategory} onChange={(e) => setBulkCategory(e.target.value)} style={{ maxWidth: "220px" }}>
                    <option value="" disabled>
                      Set category…
                    </option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.name}>
                        {c.icon} {c.name}
                      </option>
                    ))}
                  </select>
                  <button
                    className="btn btnSmall"
                    onClick={handleBulkApply}
                    disabled={!bulkCategory || bulkApplying}
                  >
                    {bulkApplying ? "Applying…" : `Apply to ${selectedIds.size} selected`}
                  </button>
                  <button className="btn btnSecondary btnSmall" onClick={() => setSelectedIds(new Set())}>
                    Clear selection
                  </button>
                </div>
              )}
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>
                        <input
                          type="checkbox"
                          checked={selectedIds.size === transactions.length}
                          onChange={toggleSelectAll}
                          aria-label="Select all"
                        />
                      </th>
                      <th>Date</th>
                      <th>Description</th>
                      <th>Account</th>
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
                        <td data-label="Select">
                          <input
                            type="checkbox"
                            checked={selectedIds.has(txn.id)}
                            onChange={() => toggleSelected(txn.id)}
                            aria-label={`Select ${txn.description}`}
                          />
                        </td>
                        <td data-label="Date">{formatDate(txn.date)}</td>
                        <td data-label="Description">{txn.description}</td>
                        <td data-label="Account">{accountLabel(accounts, txn.account_id)}</td>
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

        <div className="spacer card" style={{ borderColor: "var(--danger)" }}>
          <p className="statLabel" style={{ color: "var(--danger)" }}>
            Danger zone
          </p>
          <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "0.3rem" }}>
            Permanently deletes every transaction across every account. Account balances that
            depend on transaction history will need to be set manually afterwards.
          </p>
          <button
            className="btn btnDanger btnSmall"
            style={{ marginTop: "0.6rem" }}
            onClick={handleClearAll}
            disabled={clearingAll}
          >
            {clearingAll ? "Clearing…" : "Clear all transactions"}
          </button>
        </div>
      </div>
    </main>
  );
}
