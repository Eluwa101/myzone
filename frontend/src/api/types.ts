export type CustomerStatus = "lead" | "customer" | "inactive";

export interface Transaction {
  id: string;
  customer_id: string;
  date: string;
  item: string;
  qty: number;
  amount: number;
  currency: string;
}

export interface Customer {
  id: string;
  org_id: string;
  name: string;
  phone?: string | null;
  email?: string | null;
  job?: string | null;
  nationality?: string | null;
  pet?: string | null;
  birthday?: string | null;
  address?: string | null;
  notes?: string | null;
  interests?: string | null;
  status: CustomerStatus;
  status_auto: boolean;
  consent_date?: string | null;
  extra: Record<string, string>;
  created_at: string;
  updated_at: string;
  transactions: Transaction[];
}

export interface CustomerListResult {
  items: Customer[];
  total: number;
  page: number;
  page_size: number;
}

export interface MonthTotal {
  month: string;
  totals: Record<string, number>;
}

export interface TopCustomer {
  customer_id: string;
  name: string;
  currency: string;
  total: number;
}

export interface InterestRollup {
  interest: string;
  customers: string[];
}

export interface Summary {
  total_customers: number;
  status_counts: Record<string, number>;
  without_consent: number;
  all_time_by_currency: Record<string, number>;
  this_month_by_currency: Record<string, number>;
  last_6_months: MonthTotal[];
  top_customers: TopCustomer[];
  interests: InterestRollup[];
}

export interface PendingAction {
  id: string;
  tool_name: string;
  description: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface DuplicateGroup {
  keep: Customer;
  duplicates: Customer[];
}
