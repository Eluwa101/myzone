import { api, setToken } from "./client";

export interface User {
  id: string;
  org_id: string;
  email: string;
  role: string;
}

export async function signup(orgName: string, email: string, password: string): Promise<void> {
  const { access_token } = await api.post<{ access_token: string }>("/api/auth/signup", {
    org_name: orgName,
    email,
    password,
  });
  setToken(access_token);
}

export async function login(email: string, password: string): Promise<void> {
  const { access_token } = await api.post<{ access_token: string }>("/api/auth/login", { email, password });
  setToken(access_token);
}

export function logout(): void {
  setToken(null);
}

export function me(): Promise<User> {
  return api.get<User>("/api/auth/me");
}
