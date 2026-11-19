import { api, queryString, type Paged } from "./client";
import type { Order } from "./types";

export interface OrderWithCustomer extends Order {
  customer_name: string;
}

export function listAllOrders(params: { pending?: boolean } = {}): Promise<OrderWithCustomer[]> {
  const qs = new URLSearchParams();
  if (params.pending) qs.set("pending", "true");
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return api.get<OrderWithCustomer[]>(`/api/orders${suffix}`);
}

export function listAllOrdersPaged(params: { pending?: boolean; search?: string; page: number; pageSize: number }): Promise<Paged<OrderWithCustomer>> {
  return api.getPaged<OrderWithCustomer>(
    `/api/orders${queryString({ pending: params.pending, search: params.search, page: params.page, page_size: params.pageSize })}`
  );
}
