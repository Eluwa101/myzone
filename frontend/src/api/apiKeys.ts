import { api } from "./client";

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface CreatedApiKey extends ApiKey {
  /** the full key - only ever returned once, right after creating it */
  key: string;
}

export function listApiKeys(): Promise<ApiKey[]> {
  return api.get<ApiKey[]>("/api/api-keys");
}

export function createApiKey(name: string): Promise<CreatedApiKey> {
  return api.post<CreatedApiKey>("/api/api-keys", { name });
}

export function revokeApiKey(id: string): Promise<void> {
  return api.delete<void>(`/api/api-keys/${id}`);
}
