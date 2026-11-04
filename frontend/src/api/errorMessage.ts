import { ApiError } from "./client";

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const d = err.detail;
    if (typeof d === "string") return d;
    if (d && typeof d === "object" && "message" in d) return String((d as { message: unknown }).message);
    if (Array.isArray(d)) return d.map((e) => (typeof e === "object" && e && "msg" in e ? String((e as { msg: unknown }).msg) : String(e))).join(", ");
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}
