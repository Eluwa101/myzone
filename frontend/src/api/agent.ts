import { api } from "./client";
import type { PendingAction } from "./types";

export interface ChatResponse {
  reply: string;
  pending_actions: PendingAction[];
}

export function sendChat(message: string): Promise<ChatResponse> {
  return api.post<ChatResponse>("/api/agent/chat", { message });
}

export function listPending(): Promise<PendingAction[]> {
  return api.get<PendingAction[]>("/api/agent/pending");
}

export function confirmPending(id: string): Promise<Record<string, unknown>> {
  return api.post<Record<string, unknown>>(`/api/agent/pending/${id}/confirm`);
}

export function rejectPending(id: string): Promise<void> {
  return api.post<void>(`/api/agent/pending/${id}/reject`);
}
