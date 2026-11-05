import { api } from "./client";
import type { PendingAction } from "./types";

export interface ChatResponse {
  reply: string;
  pending_actions: PendingAction[];
}

export interface ChatThread {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatHistoryMessage {
  role: "user" | "assistant";
  content: string;
  has_image: boolean;
  created_at: string;
}

export function sendChat(message: string, threadId?: string, imageDataUrl?: string): Promise<ChatResponse> {
  return api.post<ChatResponse>("/api/agent/chat", { message, thread_id: threadId, image_data_url: imageDataUrl });
}

export function listThreads(): Promise<ChatThread[]> {
  return api.get<ChatThread[]>("/api/agent/threads");
}

export function getThreadMessages(threadId: string): Promise<ChatHistoryMessage[]> {
  return api.get<ChatHistoryMessage[]>(`/api/agent/threads/${threadId}/messages`);
}

export function deleteThread(threadId: string): Promise<void> {
  return api.delete<void>(`/api/agent/threads/${threadId}`);
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

export function askData(question: string): Promise<{ answer: string }> {
  return api.post<{ answer: string }>("/api/agent/ask", { question });
}
