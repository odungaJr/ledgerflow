export interface Account {
  id: string;
  name: string;
  bank: string;
  currency: string;
  is_active: boolean;
  created_at: string;
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

export interface DashboardSummaryResponse {
  summary: MonthlySummary;
  budget_alerts: BudgetStatus[];
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
