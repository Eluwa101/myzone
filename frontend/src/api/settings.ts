import { api } from "./client";

export interface OrgSettings {
  biz_name: string | null;
  whatsapp_number: string | null;
  default_country_code: string | null;
  qr_message: string | null;
  industry: string | null;
  team_size: number | null;
  phone: string | null;
  address: string | null;
  brand_color: string | null;
  manager_name: string | null;
  staff_names: string[] | null;
  default_currency: string | null;
  support_email: string | null;
  sender_handle: string | null;
  sender_domain?: string | null;
}

export function getSettings(): Promise<OrgSettings> {
  return api.get<OrgSettings>("/api/settings");
}

export async function updateSettings(data: Partial<OrgSettings>): Promise<OrgSettings> {
  const saved = await api.put<OrgSettings>("/api/settings", data);
  // settings other pages cached at first read may have just changed
  cachedDefaultCountryCode = null;
  return saved;
}

let cachedDefaultCountryCode: Promise<string> | null = null;

/** The org's default country calling code ("234"), or "" - used to complete
 * customer phone numbers saved in local format when building WhatsApp links. */
export function getDefaultCountryCode(): Promise<string> {
  if (!cachedDefaultCountryCode) {
    cachedDefaultCountryCode = getSettings()
      .then((s) => s.default_country_code ?? "")
      .catch(() => {
        cachedDefaultCountryCode = null; // don't cache a failed fetch (e.g. server still waking)
        return "";
      });
  }
  return cachedDefaultCountryCode;
}

let cachedDefaultCurrency: Promise<string> | null = null;

/** The org's configured default currency, fetched once per page load and
 * cached - used to prefill new transaction/order forms so staff don't have
 * to pick a currency every time. */
export function getDefaultCurrency(): Promise<string> {
  if (!cachedDefaultCurrency) {
    cachedDefaultCurrency = getSettings()
      .then((s) => s.default_currency ?? "")
      .catch(() => "");
  }
  return cachedDefaultCurrency;
}
