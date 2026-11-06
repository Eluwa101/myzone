import { api } from "./client";
import type { Segment, SegmentFilters, SegmentResult } from "./types";

export interface SegmentInput {
  name: string;
  filters: SegmentFilters;
}

export function listSegments(): Promise<Segment[]> {
  return api.get<Segment[]>("/api/segments");
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

export function suggestSegmentFilters(description: string): Promise<SegmentFilters> {
  return api.post<SegmentFilters>("/api/segments/suggest", { description });
}
