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

export interface OrderItem {
  name: string;
  qty: number;
}

export interface Order {
  id: string;
  customer_id: string;
  order_date: string;
  delivery_date?: string | null;
  items: OrderItem[];
  amount?: number | null;
  currency?: string | null;
  paid: boolean;
  delivered: boolean;
  notes?: string | null;
}

export interface NoteCustomerSummary {
  id: string;
  name: string;
}

export interface OrgNote {
  id: string;
  title: string;
  content: string;
  is_pending_review: boolean;
  created_by_agent: boolean;
  created_at: string;
  updated_at: string;
  customers: NoteCustomerSummary[];
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
  orders: Order[];
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

export interface InterestCustomer {
  id: string;
  name: string;
}

export interface InterestRollup {
  interest: string;
  customers: InterestCustomer[];
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
  range_start?: string | null;
  range_end?: string | null;
}

export type FormFieldType = "text" | "textarea" | "tel" | "email" | "number" | "date";
export type FormFieldCategory = "customer" | "transaction" | "custom";

export interface FormFieldDef {
  key: string;
  label: string;
  type: FormFieldType;
  required: boolean;
  category: FormFieldCategory;
}

export interface CustomForm {
  id: string;
  name: string;
  public_token: string;
  fields: FormFieldDef[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PublicForm {
  name: string;
  fields: FormFieldDef[];
}

export interface FormSubmission {
  id: string;
  customer_id: string | null;
  customer_name: string | null;
  raw_payload: Record<string, string>;
  created_at: string;
}

export interface SegmentFilters {
  status?: CustomerStatus | null;
  interest_contains?: string | null;
  has_consent?: boolean | null;
  search?: string | null;
  last_purchase_within_days?: number | null;
  last_purchase_over_days?: number | null;
  min_transactions?: number | null;
}

export interface Segment {
  id: string;
  name: string;
  filters: SegmentFilters;
  created_at: string;
  updated_at: string;
}

export interface SegmentMember {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  status: CustomerStatus;
}

export interface SegmentResult {
  total: number;
  members: SegmentMember[];
}

export interface SavedWidget {
  id: string;
  question: string;
  title: string;
  created_at: string;
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

export interface ImportResult {
  added: number;
  merged: number;
  skipped: number;
  failed: number;
  errors: string[];
}
