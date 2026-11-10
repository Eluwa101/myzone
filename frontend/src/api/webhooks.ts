import { api } from "./client";
import type { WebhookDelivery, WebhookSubscription } from "./types";

export interface WebhookSubscriptionInput {
  target_url: string;
  event_types: string[];
}

export function listEventTypes(): Promise<string[]> {
  return api.get<string[]>("/api/webhooks/event-types");
}

export function listSubscriptions(): Promise<WebhookSubscription[]> {
  return api.get<WebhookSubscription[]>("/api/webhooks");
}

export function createSubscription(data: WebhookSubscriptionInput): Promise<WebhookSubscription> {
  return api.post<WebhookSubscription>("/api/webhooks", data);
}

export function updateSubscription(
  id: string,
  data: Partial<WebhookSubscriptionInput> & { is_active?: boolean; regenerate_secret?: boolean }
): Promise<WebhookSubscription> {
  return api.patch<WebhookSubscription>(`/api/webhooks/${id}`, data);
}

export function deleteSubscription(id: string): Promise<void> {
  return api.delete<void>(`/api/webhooks/${id}`);
}

export function listDeliveries(id: string): Promise<WebhookDelivery[]> {
  return api.get<WebhookDelivery[]>(`/api/webhooks/${id}/deliveries`);
}
