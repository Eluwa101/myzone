export const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "mini_crm_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

// Render's free tier spins the backend down after ~15min idle; the first
// request after that takes 30-60s to connect instead of failing outright.
// Retry on network-level failures (not HTTP error responses) and surface a
// "waking up" flag so the UI can show a friendly message instead of a raw
// fetch error.
const WAKE_RETRY_ATTEMPTS = 10;
const WAKE_RETRY_DELAY_MS = 4000;

let wakingUp = false;
const wakeListeners = new Set<(waking: boolean) => void>();

function setWakingUp(value: boolean): void {
  if (wakingUp === value) return;
  wakingUp = value;
  wakeListeners.forEach((listener) => listener(wakingUp));
}

export function isServerWaking(): boolean {
  return wakingUp;
}

export function subscribeServerWaking(listener: (waking: boolean) => void): () => void {
  wakeListeners.add(listener);
  return () => wakeListeners.delete(listener);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchWithWakeRetry(input: string, init: RequestInit): Promise<Response> {
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(input, init);
      setWakingUp(false);
      return res;
    } catch (err) {
      if (attempt >= WAKE_RETRY_ATTEMPTS) {
        setWakingUp(false);
        throw err;
      }
      setWakingUp(true);
      await sleep(WAKE_RETRY_DELAY_MS);
    }
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (options.body !== undefined) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let res: Response;
  try {
    res = await fetchWithWakeRetry(`${BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new ApiError(0, "Could not reach the server. Please check your connection and try again.");
  }

  if (res.status === 204) return undefined as T;

  const isJson = res.headers.get("content-type")?.includes("application/json") ?? false;
  const body = isJson ? await res.json() : await res.text();

  if (!res.ok) {
    if (res.status === 401) setToken(null);
    const detail = isJson && body && typeof body === "object" && "detail" in body ? body.detail : body;
    throw new ApiError(res.status, detail);
  }
  return body as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(body ?? {}) }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body ?? {}) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
