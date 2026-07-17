import type {
  Account,
  BudgetStatus,
  Category,
  DashboardInsightsResponse,
  DashboardSummaryResponse,
  ImportResult,
  Transaction,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function extractErrorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === "string") return body.detail;
    if (body.detail) return JSON.stringify(body.detail);
  } catch {
    // response body wasn't JSON — fall through to statusText
  }
  return res.statusText || `Request failed with status ${res.status}`;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    throw new ApiError(res.status, await extractErrorDetail(res));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ── Accounts ─────────────────────────────────────────────────────────────────

export const getAccounts = (includeInactive = false) =>
  request<Account[]>(`/accounts${includeInactive ? "?include_inactive=true" : ""}`);

export const createAccount = (data: { name: string; bank: string; currency?: string }) =>
  request<Account>("/accounts", { method: "POST", body: JSON.stringify(data) });

export const updateAccount = (
  id: string,
  data: Partial<Pick<Account, "name" | "bank" | "currency" | "is_active">>
) => request<Account>(`/accounts/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const deleteAccount = (id: string) =>
  request<{ status: string; id: string }>(`/accounts/${id}`, { method: "DELETE" });

// ── Categories ───────────────────────────────────────────────────────────────

export const getCategories = () => request<Category[]>("/categories");

// ── Transactions ─────────────────────────────────────────────────────────────

export const getTransactions = (params?: {
  account_id?: string;
  category?: string;
  limit?: number;
}) => {
  const qs = new URLSearchParams();
  if (params?.account_id) qs.set("account_id", params.account_id);
  if (params?.category) qs.set("category", params.category);
  if (params?.limit) qs.set("limit", String(params.limit));
  const query = qs.toString();
  return request<Transaction[]>(`/transactions${query ? `?${query}` : ""}`);
};

export const patchTransaction = (
  id: string,
  data: { category_name?: string; notes?: string; is_confirmed?: boolean }
) => request<{ status: string; id: string }>(`/transactions/${id}`, {
  method: "PATCH",
  body: JSON.stringify(data),
});

export const deleteTransaction = (id: string) =>
  request<{ status: string; id: string }>(`/transactions/${id}`, { method: "DELETE" });

export async function importCsv(
  accountId: string,
  file: File,
  autoCategorise = true
): Promise<ImportResult> {
  const form = new FormData();
  form.append("account_id", accountId);
  form.append("file", file);
  form.append("auto_categorise", String(autoCategorise));
  const res = await fetch(`${API_URL}/transactions/import/csv`, { method: "POST", body: form });
  if (!res.ok) {
    throw new ApiError(res.status, await extractErrorDetail(res));
  }
  return res.json();
}

// ── Budgets ──────────────────────────────────────────────────────────────────

export const getBudgets = () => request<BudgetStatus[]>("/budgets");

export const createBudget = (data: {
  category_name: string;
  limit_amount: number;
  period: string;
  start_date: string;
}) =>
  request<{ id: string; category: string; limit: number }>("/budgets", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updateBudget = (id: string, data: { limit_amount?: number; is_active?: boolean }) =>
  request<{ status: string; id: string }>(`/budgets/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

export const deleteBudget = (id: string) =>
  request<{ status: string; id: string }>(`/budgets/${id}`, { method: "DELETE" });

// ── Dashboard ────────────────────────────────────────────────────────────────

export const getDashboardSummary = (year?: number, month?: number) => {
  const qs = new URLSearchParams();
  if (year) qs.set("year", String(year));
  if (month) qs.set("month", String(month));
  const query = qs.toString();
  return request<DashboardSummaryResponse>(`/dashboard/summary${query ? `?${query}` : ""}`);
};

export const getDashboardInsights = (year?: number, month?: number) => {
  const qs = new URLSearchParams();
  if (year) qs.set("year", String(year));
  if (month) qs.set("month", String(month));
  const query = qs.toString();
  return request<DashboardInsightsResponse>(`/dashboard/insights${query ? `?${query}` : ""}`);
};
