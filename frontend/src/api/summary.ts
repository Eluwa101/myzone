import { api } from "./client";
import type { MonthTotal, Summary, TopCustomer } from "./types";

export interface DateRangeParams {
  startDate?: string;
  endDate?: string;
}

function qs(params: DateRangeParams): string {
  const q = new URLSearchParams();
  if (params.startDate) q.set("start_date", params.startDate);
  if (params.endDate) q.set("end_date", params.endDate);
  const s = q.toString();
  return s ? `?${s}` : "";
}

export function getSummary(params: DateRangeParams = {}): Promise<Summary> {
  return api.get<Summary>(`/api/summary${qs(params)}`);
}

export function getTopCustomers(params: DateRangeParams = {}, limit = 50): Promise<TopCustomer[]> {
  const q = new URLSearchParams();
  if (params.startDate) q.set("start_date", params.startDate);
  if (params.endDate) q.set("end_date", params.endDate);
  q.set("limit", String(limit));
  return api.get<TopCustomer[]>(`/api/summary/top-customers?${q.toString()}`);
}

export function getMonthly(params: DateRangeParams = {}): Promise<MonthTotal[]> {
  return api.get<MonthTotal[]>(`/api/summary/monthly${qs(params)}`);
}
