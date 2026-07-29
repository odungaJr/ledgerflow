export interface Account {
  id: string;
  name: string;
  bank: string;
  currency: string;
  is_active: boolean;
  created_at: string;
  manual_balance: number | null;
  manual_balance_date: string | null;
  current_balance: number | null;
  balance_as_of: string | null;
  balance_source: "transaction" | "manual" | null;
}

export interface Category {
  id: string;
  name: string;
  icon: string;
  is_income: boolean;
}

export interface Transaction {
  id: string;
  account_id: string;
  date: string;
  description: string;
  amount: number;
  type: "debit" | "credit";
  balance_after: number | null;
  category: string | null;
  ai_confidence: number | null;
  is_confirmed: boolean;
  notes: string | null;
}

export interface BudgetStatus {
  budget_id: string;
  category_name: string;
  period: "monthly" | "weekly";
  limit: number;
  spent: number;
  remaining: number;
  pct_used: number;
  is_breached: boolean;
  is_warning: boolean;
}

export interface TopCategory {
  name: string;
  total: number;
  budget_limit: number | null;
}

export interface MonthlySummary {
  period: string;
  total_income: number;
  total_expenses: number;
  net: number;
  currency: string;
  top_categories: TopCategory[];
  anomalies: unknown[];
}

export interface IncomeEntry {
  id: string;
  series_id: string | null;
  source: string;
  category: string | null;
  expected_amount: number;
  expected_date: string;
  received_amount: number;
  received_date: string | null;
  is_recurring: boolean;
  recurrence_period: "monthly" | "weekly" | null;
  status: "pending" | "partial" | "received" | "overdue";
  pending_amount: number;
  notes: string | null;
}

export interface IncomeSummary {
  total_expected: number;
  total_received: number;
  total_pending: number;
  pending_count: number;
  overdue_count: number;
}

export interface Asset {
  id: string;
  name: string;
  asset_type: "cash" | "stocks" | "bonds" | "real_estate" | "vehicle" | "other";
  quantity: number | null;
  currency: string;
  is_active: boolean;
  notes: string | null;
  current_value: number | null;
  value_date: string | null;
  change_amount: number | null;
}

export interface AssetValueSnapshot {
  id: string;
  value_date: string;
  unit_value: number | null;
  total_value: number;
}

export interface AssetSummaryRow {
  id: string;
  name: string;
  asset_type: string;
  quantity: number | null;
  currency: string;
  current_value: number;
  value_date: string;
  change_amount: number;
  change_pct: number;
}

export interface AssetsSummary {
  total_value: number;
  breakdown: { asset_type: string; total: number }[];
  assets: AssetSummaryRow[];
  trend: { date: string; total_value: number }[];
}

export interface DashboardSummaryResponse {
  summary: MonthlySummary;
  budget_alerts: BudgetStatus[];
  income_tracker: IncomeSummary;
  income_all_time: IncomeSummary;
  assets: AssetsSummary;
}

export interface DashboardInsightsResponse {
  period: string;
  summary: MonthlySummary;
  anomalies: unknown[];
  narrative: string;
}

export interface ImportResult {
  inserted: number;
  skipped: number;
  total_parsed: number;
  categorised: boolean;
}
