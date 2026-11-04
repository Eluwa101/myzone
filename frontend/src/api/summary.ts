import { api } from "./client";
import type { Summary } from "./types";

export function getSummary(): Promise<Summary> {
  return api.get<Summary>("/api/summary");
}
