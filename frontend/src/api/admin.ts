import { api, getToken, setToken } from "./client";

/** Platform admins opening another business's account to help.
 *
 * Entering swaps the app's login token for a short-lived admin session for
 * that business, and keeps the admin's own token aside so "Back to my
 * account" (or the session expiring) can restore it. */

const RETURN_TOKEN_KEY = "myshop_admin_return_token";
const SESSION_KEY = "myshop_admin_session";

export interface AdminOrg {
  id: string;
  name: string;
  owner_email: string | null;
  customers: number;
  created_at: string;
  closing: boolean;
  is_home: boolean;
}

export interface AdminSessionInfo {
  org_id: string;
  org_name: string;
  expires_at: string;
}

export function listAdminOrgs(): Promise<AdminOrg[]> {
  return api.get<AdminOrg[]>("/api/admin/orgs");
}

export function currentAdminSession(): AdminSessionInfo | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw && localStorage.getItem(RETURN_TOKEN_KEY) ? (JSON.parse(raw) as AdminSessionInfo) : null;
  } catch {
    return null;
  }
}

export async function enterBusiness(orgId: string): Promise<void> {
  const session = await api.post<AdminSessionInfo & { access_token: string }>("/api/admin/impersonate", { org_id: orgId });
  // switching from one business straight to another keeps the original return token
  if (!localStorage.getItem(RETURN_TOKEN_KEY)) {
    const own = getToken();
    if (own) localStorage.setItem(RETURN_TOKEN_KEY, own);
  }
  localStorage.setItem(SESSION_KEY, JSON.stringify({ org_id: session.org_id, org_name: session.org_name, expires_at: session.expires_at }));
  setToken(session.access_token);
  window.location.assign("/customers");
}

/** Restores the admin's own login. Returns false if there was no admin
 * session to leave. */
export function restoreOwnAccount(): boolean {
  const own = localStorage.getItem(RETURN_TOKEN_KEY);
  localStorage.removeItem(RETURN_TOKEN_KEY);
  localStorage.removeItem(SESSION_KEY);
  if (!own) return false;
  setToken(own);
  return true;
}

export async function leaveBusiness(): Promise<void> {
  try {
    await api.post<void>("/api/admin/stop", {});
  } catch {
    // the session may already have expired - leaving still works
  }
  restoreOwnAccount();
  window.location.assign("/customers");
}
