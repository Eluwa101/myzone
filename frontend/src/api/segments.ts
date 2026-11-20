import { api, queryString, type Paged } from "./client";
import type { Segment, SegmentChanges, SegmentFieldsCatalog, SegmentFilters, SegmentResult } from "./types";

export interface SegmentInput {
  name: string;
  filters: SegmentFilters;
  /** "" switches a segment back to its visual filters */
  sql?: string;
}

export interface SandboxTable {
  name: string;
  columns: { name: string; type: string; description: string }[];
}

export function listSegments(): Promise<Segment[]> {
  return api.get<Segment[]>("/api/segments");
}

export function getSegment(id: string): Promise<Segment> {
  return api.get<Segment>(`/api/segments/${id}`);
}

export function createSegment(data: SegmentInput): Promise<Segment> {
  return api.post<Segment>("/api/segments", data);
}

export function updateSegment(id: string, data: Partial<SegmentInput>): Promise<Segment> {
  return api.patch<Segment>(`/api/segments/${id}`, data);
}

export function deleteSegment(id: string): Promise<void> {
  return api.delete<void>(`/api/segments/${id}`);
}

export function previewSegment(filters: SegmentFilters): Promise<SegmentResult> {
  return api.post<SegmentResult>("/api/segments/preview", filters);
}

export function getSegmentMembers(id: string): Promise<SegmentResult> {
  return api.get<SegmentResult>(`/api/segments/${id}/members`);
}

/** Who matches the definition now but isn't in the list yet, and who is in the list but no longer matches. */
export function getSegmentChanges(id: string): Promise<SegmentChanges> {
  return api.get<SegmentChanges>(`/api/segments/${id}/changes`);
}

/** "add" keeps the list and adds new matches; "rerun" replaces it with exactly who matches now. */
export function refreshSegment(id: string, mode: "add" | "rerun"): Promise<{ added: number; removed: number; total: number }> {
  return api.post<{ added: number; removed: number; total: number }>(`/api/segments/${id}/refresh`, { mode });
}

export function suggestSegmentFilters(description: string): Promise<SegmentFilters> {
  return api.post<SegmentFilters>("/api/segments/suggest", { description });
}

export function getSegmentFields(): Promise<SegmentFieldsCatalog> {
  return api.get<SegmentFieldsCatalog>("/api/segments/fields");
}

export function getSqlSchema(): Promise<SandboxTable[]> {
  return api.get<SandboxTable[]>("/api/segments/sql/schema");
}

export function previewSqlSegment(sql: string): Promise<SegmentResult> {
  return api.post<SegmentResult>("/api/segments/sql/preview", { sql });
}

export function suggestSegmentSql(description: string, currentSql: string | null): Promise<{ sql: string }> {
  return api.post<{ sql: string }>("/api/segments/sql/suggest", { description, current_sql: currentSql });
}

export function listSegmentsPaged(params: { search?: string; page: number; pageSize: number }): Promise<Paged<Segment>> {
  return api.getPaged<Segment>(`/api/segments${queryString({ search: params.search, page: params.page, page_size: params.pageSize })}`);
}
