import type {
  Account,
  Asset,
  AssetValueSnapshot,
  AssetsSummary,
  BudgetStatus,
  Category,
  DashboardInsightsResponse,
  DashboardSummaryResponse,
  ImportResult,
  IncomeEntry,
  IncomeSummary,
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
    credentials: "include",
    ...options,
  });
  if (!res.ok) {
    throw new ApiError(res.status, await extractErrorDetail(res));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export const getAuthStatus = () => request<{ initialized: boolean }>("/auth/status");

export const register = (username: string, password: string) =>
  request<{ username: string }>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });

export const login = (username: string, password: string) =>
  request<{ username: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });

export const logout = () => request<{ status: string }>("/auth/logout", { method: "POST" });

export const getMe = () => request<{ username: string }>("/auth/me");

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
  from_date?: string;
  to_date?: string;
  txn_type?: string;
  search?: string;
  limit?: number;
  offset?: number;
}) => {
  const qs = new URLSearchParams();
  if (params?.account_id) qs.set("account_id", params.account_id);
  if (params?.category) qs.set("category", params.category);
  if (params?.from_date) qs.set("from_date", params.from_date);
  if (params?.to_date) qs.set("to_date", params.to_date);
  if (params?.txn_type) qs.set("txn_type", params.txn_type);
  if (params?.search) qs.set("search", params.search);
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
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

export const bulkPatchTransactions = (transactionIds: string[], categoryName: string) =>
  request<{ updated: number }>("/transactions/bulk", {
    method: "PATCH",
    body: JSON.stringify({ transaction_ids: transactionIds, category_name: categoryName }),
  });

export const deleteTransaction = (id: string) =>
  request<{ status: string; id: string }>(`/transactions/${id}`, { method: "DELETE" });

export async function importStatement(
  accountId: string,
  file: File,
  fileType: "csv" | "pdf",
  autoCategorise = true
): Promise<ImportResult> {
  const form = new FormData();
  form.append("account_id", accountId);
  form.append("file", file);
  form.append("auto_categorise", String(autoCategorise));
  const res = await fetch(`${API_URL}/transactions/import/${fileType}`, {
    method: "POST",
    body: form,
    credentials: "include",
  });
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

// ── Income ───────────────────────────────────────────────────────────────────

export const getIncomeEntries = (year?: number, month?: number) => {
  const qs = new URLSearchParams();
  if (year) qs.set("year", String(year));
  if (month) qs.set("month", String(month));
  const query = qs.toString();
  return request<IncomeEntry[]>(`/income${query ? `?${query}` : ""}`);
};

export const getIncomeSummary = (year?: number, month?: number) => {
  const qs = new URLSearchParams();
  if (year) qs.set("year", String(year));
  if (month) qs.set("month", String(month));
  const query = qs.toString();
  return request<IncomeSummary>(`/income/summary${query ? `?${query}` : ""}`);
};

export const createIncomeEntry = (data: {
  source: string;
  expected_amount: number;
  expected_date: string;
  category_name?: string;
  is_recurring?: boolean;
  recurrence_period?: string;
  notes?: string;
}) => request<IncomeEntry>("/income", { method: "POST", body: JSON.stringify(data) });

export const patchIncomeEntry = (
  id: string,
  data: {
    received_amount?: number;
    received_date?: string;
    expected_amount?: number;
    expected_date?: string;
    notes?: string;
  }
) => request<IncomeEntry>(`/income/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const deleteIncomeEntry = (id: string) =>
  request<{ status: string; id: string }>(`/income/${id}`, { method: "DELETE" });

// ── Assets ───────────────────────────────────────────────────────────────────

export const getAssets = () => request<Asset[]>("/assets");

export const createAsset = (data: {
  name: string;
  asset_type: string;
  quantity?: number;
  currency?: string;
  value_date: string;
  total_value: number;
  unit_value?: number;
  notes?: string;
}) => request<Asset>("/assets", { method: "POST", body: JSON.stringify(data) });

export const patchAsset = (
  id: string,
  data: Partial<Pick<Asset, "name" | "asset_type" | "quantity" | "currency" | "is_active" | "notes">>
) => request<Asset>(`/assets/${id}`, { method: "PATCH", body: JSON.stringify(data) });

export const addAssetValue = (
  id: string,
  data: { value_date: string; total_value: number; unit_value?: number }
) => request<Asset>(`/assets/${id}/values`, { method: "POST", body: JSON.stringify(data) });

export const getAssetHistory = (id: string) => request<AssetValueSnapshot[]>(`/assets/${id}/history`);

export const deleteAsset = (id: string) =>
  request<{ status: string; id: string }>(`/assets/${id}`, { method: "DELETE" });

export const getAssetsSummary = () => request<AssetsSummary>("/assets/summary");

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
