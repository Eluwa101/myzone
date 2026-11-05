import { api } from "./client";
import type { Customer, CustomerListResult, CustomerStatus, DuplicateGroup, ImportResult, Order, OrderItem, Transaction } from "./types";

export interface CustomerInput {
  name: string;
  phone?: string;
  email?: string;
  job?: string;
  nationality?: string;
  pet?: string;
  birthday?: string;
  address?: string;
  notes?: string;
  interests?: string;
  status?: CustomerStatus;
  consent_date?: string;
  extra?: Record<string, string>;
}

export interface ListParams {
  search?: string;
  status?: CustomerStatus | "";
  page?: number;
  pageSize?: number;
}

export function listCustomers(params: ListParams = {}): Promise<CustomerListResult> {
  const qs = new URLSearchParams();
  if (params.search) qs.set("search", params.search);
  if (params.status) qs.set("status_filter", params.status);
  qs.set("page", String(params.page ?? 1));
  qs.set("page_size", String(params.pageSize ?? 20));
  return api.get<CustomerListResult>(`/api/customers?${qs.toString()}`);
}

export function getCustomer(id: string): Promise<Customer> {
  return api.get<Customer>(`/api/customers/${id}`);
}

export function createCustomer(data: CustomerInput, force = false): Promise<Customer> {
  return api.post<Customer>(`/api/customers${force ? "?force=true" : ""}`, data);
}

export function updateCustomer(id: string, data: Partial<CustomerInput>): Promise<Customer> {
  return api.patch<Customer>(`/api/customers/${id}`, data);
}

export function deleteCustomer(id: string): Promise<void> {
  return api.delete<void>(`/api/customers/${id}`);
}

export function findDuplicates(): Promise<DuplicateGroup[]> {
  return api.get<DuplicateGroup[]>("/api/customers/duplicates");
}

export function mergeCustomers(keepId: string, mergeId: string): Promise<Customer> {
  return api.post<Customer>("/api/customers/merge", { keep_id: keepId, merge_id: mergeId });
}

export type TransactionInput = Pick<Transaction, "date" | "item" | "qty" | "amount" | "currency">;

export function addTransaction(customerId: string, data: TransactionInput): Promise<Transaction> {
  return api.post<Transaction>(`/api/customers/${customerId}/transactions`, data);
}

export function updateTransaction(customerId: string, txId: string, data: Partial<TransactionInput>): Promise<Transaction> {
  return api.patch<Transaction>(`/api/customers/${customerId}/transactions/${txId}`, data);
}

export function deleteTransaction(customerId: string, txId: string): Promise<void> {
  return api.delete<void>(`/api/customers/${customerId}/transactions/${txId}`);
}

export interface OrderInput {
  order_date: string;
  delivery_date?: string | null;
  items: OrderItem[];
  amount?: number | null;
  currency?: string | null;
  paid?: boolean;
  delivered?: boolean;
  notes?: string | null;
}

export function addOrder(customerId: string, data: OrderInput): Promise<Order> {
  return api.post<Order>(`/api/customers/${customerId}/orders`, data);
}

export function updateOrder(customerId: string, orderId: string, data: Partial<OrderInput>): Promise<Order> {
  return api.patch<Order>(`/api/customers/${customerId}/orders/${orderId}`, data);
}

export function deleteOrder(customerId: string, orderId: string): Promise<void> {
  return api.delete<void>(`/api/customers/${customerId}/orders/${orderId}`);
}

export function exportCsv(): Promise<string> {
  return api.get<string>("/api/customers/export");
}

export function importCsv(csvText: string): Promise<ImportResult> {
  return api.post<ImportResult>("/api/customers/import", { csv_text: csvText });
}
