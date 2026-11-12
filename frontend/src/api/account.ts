import { api } from "./client";

export interface ClosureStatus {
  business_name: string;
  closing: boolean;
  requested_at: string | null;
  scheduled_for: string | null;
  requested_by: string | null;
  grace_days: number;
}

/** Fired after closure is requested or cancelled, so the app-wide banner
 * updates without a reload. */
export const CLOSURE_CHANGED_EVENT = "myshop:closure-changed";

export function getClosure(): Promise<ClosureStatus> {
  return api.get<ClosureStatus>("/api/account/closure");
}

export async function requestClosure(confirmName: string): Promise<ClosureStatus> {
  const status = await api.post<ClosureStatus>("/api/account/closure", { confirm_name: confirmName });
  window.dispatchEvent(new Event(CLOSURE_CHANGED_EVENT));
  return status;
}

export async function cancelClosure(): Promise<ClosureStatus> {
  const status = await api.delete<ClosureStatus>("/api/account/closure");
  window.dispatchEvent(new Event(CLOSURE_CHANGED_EVENT));
  return status;
}

export function formatClosureDate(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" }) : "";
}
