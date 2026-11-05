import { api } from "./client";
import type { OrgNote } from "./types";

export interface NoteInput {
  title: string;
  content: string;
  customer_ids?: string[];
}

export interface NoteListParams {
  customerId?: string;
  pending?: boolean;
}

export function listNotes(params: NoteListParams = {}): Promise<OrgNote[]> {
  const qs = new URLSearchParams();
  if (params.customerId) qs.set("customer_id", params.customerId);
  if (params.pending) qs.set("pending", "true");
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return api.get<OrgNote[]>(`/api/notes${suffix}`);
}

export function getPendingNoteCount(): Promise<{ count: number }> {
  return api.get<{ count: number }>("/api/notes/pending/count");
}

export function createNote(data: NoteInput): Promise<OrgNote> {
  return api.post<OrgNote>("/api/notes", data);
}

export function updateNote(id: string, data: Partial<NoteInput> & { is_pending_review?: boolean }): Promise<OrgNote> {
  return api.patch<OrgNote>(`/api/notes/${id}`, data);
}

export function deleteNote(id: string): Promise<void> {
  return api.delete<void>(`/api/notes/${id}`);
}
