"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  changePassword,
  createCategory,
  deleteCategory,
  getCategories,
} from "@/lib/api";
import { useTheme } from "@/components/ThemeProvider";
import type { Category } from "@/lib/types";

const THEME_OPTIONS = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "Match system" },
] as const;

export default function SettingsPage() {
  return (
    <main className="page">
      <div className="container">
        <div className="pageHeader">
          <h1>Settings</h1>
        </div>

        <AppearanceSection />
        <div className="spacer" />
        <SecuritySection />
        <div className="spacer" />
        <CategoriesSection />
      </div>
    </main>
  );
}

function AppearanceSection() {
  const { theme, setTheme } = useTheme();

  return (
    <section className="card">
      <h2 className="sectionTitle">Appearance</h2>
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
        {THEME_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            className={`btn btnSmall ${theme === opt.value ? "" : "btnSecondary"}`}
            onClick={() => setTheme(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </section>
  );
}

function SecuritySection() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (newPassword !== confirmPassword) {
      setError("New password and confirmation don't match.");
      return;
    }
    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters.");
      return;
    }

    setSubmitting(true);
    try {
      await changePassword(currentPassword, newPassword);
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to change password");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="card">
      <h2 className="sectionTitle">Security</h2>
      <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: 0 }}>
        Repeated failed login attempts temporarily lock the account, and sessions log out
        automatically after a period of inactivity.
      </p>

      <form className="form" onSubmit={handleSubmit}>
        <div className="formRow">
          <label htmlFor="current-password">Current password</label>
          <input
            id="current-password"
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>
        <div className="formRow">
          <label htmlFor="new-password">New password</label>
          <input
            id="new-password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
        </div>
        <div className="formRow">
          <label htmlFor="confirm-password">Confirm new password</label>
          <input
            id="confirm-password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
            required
          />
        </div>
        {error && <div className="alert error">{error}</div>}
        {success && <div className="alert info">Password changed.</div>}
        <button className="btn" type="submit" disabled={submitting}>
          {submitting ? "Saving…" : "Change password"}
        </button>
      </form>
    </section>
  );
}

function CategoriesSection() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [isIncome, setIsIncome] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function load() {
    getCategories()
      .then((data) => {
        setCategories(data);
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load categories"))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (!name.trim()) {
      setFormError("Category name is required.");
      return;
    }
    setSubmitting(true);
    try {
      await createCategory({ name: name.trim(), is_income: isIncome });
      setName("");
      setIsIncome(false);
      load();
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Failed to create category");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(category: Category) {
    if (!confirm(`Delete the "${category.name}" category?`)) return;
    try {
      await deleteCategory(category.id);
      load();
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Failed to delete category");
    }
  }

  const expenseCategories = categories.filter((c) => !c.is_income);
  const incomeCategories = categories.filter((c) => c.is_income);

  return (
    <section className="card">
      <h2 className="sectionTitle">Categories</h2>
      <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: 0 }}>
        Add your own categories for transactions and budgets. Built-in categories can be
        used everywhere but not renamed or removed here — batch-relabel transactions from the{" "}
        Transactions page.
      </p>

      <form className="form" onSubmit={handleCreate} style={{ maxWidth: "none" }}>
        <div className="formInline">
          <div className="formRow">
            <label htmlFor="cat-name">Name</label>
            <input id="cat-name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="formRow" style={{ flex: "0 0 auto" }}>
            <label htmlFor="cat-income">Type</label>
            <select
              id="cat-income"
              value={isIncome ? "income" : "expense"}
              onChange={(e) => setIsIncome(e.target.value === "income")}
            >
              <option value="expense">Expense</option>
              <option value="income">Income</option>
            </select>
          </div>
          <button className="btn" type="submit" disabled={submitting}>
            {submitting ? "Adding…" : "Add category"}
          </button>
        </div>
        {formError && <div className="alert error">{formError}</div>}
      </form>

      <div className="spacer" />

      {loading ? (
        <p>Loading…</p>
      ) : error ? (
        <div className="alert error">{error}</div>
      ) : categories.length === 0 ? (
        <div className="empty">No categories yet.</div>
      ) : (
        <>
          <CategoryList title="Expense categories" categories={expenseCategories} onDelete={handleDelete} />
          <div className="spacer" />
          <CategoryList title="Income categories" categories={incomeCategories} onDelete={handleDelete} />
        </>
      )}
    </section>
  );
}

function CategoryList({
  title,
  categories,
  onDelete,
}: {
  title: string;
  categories: Category[];
  onDelete: (c: Category) => void;
}) {
  return (
    <div>
      <p style={{ fontWeight: 600, fontSize: "0.85rem", marginBottom: "0.5rem" }}>{title}</p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
        {categories.map((c) => (
          <span key={c.id} className="badge neutral" style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
            {c.name}
            {!c.is_system && (
              <button
                type="button"
                onClick={() => onDelete(c)}
                aria-label={`Delete ${c.name}`}
                style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", padding: 0, fontSize: "0.75rem", textDecoration: "underline" }}
              >
                Remove
              </button>
            )}
          </span>
        ))}
      </div>
    </div>
  );
}
