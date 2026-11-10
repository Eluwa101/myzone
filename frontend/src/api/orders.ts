import { api } from "./client";
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
