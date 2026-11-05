import { api } from "./client";
import type { SavedWidget } from "./types";

export function listWidgets(): Promise<SavedWidget[]> {
  return api.get<SavedWidget[]>("/api/dashboard/widgets");
}

export function createWidget(question: string, title?: string): Promise<SavedWidget> {
  return api.post<SavedWidget>("/api/dashboard/widgets", { question, title });
}

export function deleteWidget(id: string): Promise<void> {
  return api.delete<void>(`/api/dashboard/widgets/${id}`);
}
