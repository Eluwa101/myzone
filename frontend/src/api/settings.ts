import { api } from "./client";

export interface OrgSettings {
  biz_name: string | null;
  whatsapp_number: string | null;
  qr_message: string | null;
  industry: string | null;
  team_size: number | null;
  phone: string | null;
  address: string | null;
  brand_color: string | null;
  manager_name: string | null;
  staff_names: string[] | null;
}

export function getSettings(): Promise<OrgSettings> {
  return api.get<OrgSettings>("/api/settings");
}

export function updateSettings(data: Partial<OrgSettings>): Promise<OrgSettings> {
  return api.put<OrgSettings>("/api/settings", data);
}
