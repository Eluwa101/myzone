import { api } from "./client";

export type ScanStatus = "processing" | "done" | "needs_review" | "failed";

export interface DocumentScan {
  id: string;
  status: ScanStatus;
  display_id: string | null;
  customer_id: string | null;
  document_type: string | null;
  summary: string | null;
  actions: string[];
  error: string | null;
  created_at: string;
}

export function listScans(): Promise<DocumentScan[]> {
  return api.get<DocumentScan[]>("/api/scans");
}

export function startScan(imageDataUrl: string, hint?: string): Promise<DocumentScan> {
  return api.post<DocumentScan>("/api/scans", { image_data_url: imageDataUrl, hint: hint || null });
}
