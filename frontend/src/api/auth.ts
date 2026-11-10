import { api, setToken } from "./client";

export interface User {
  id: string;
  org_id: string;
  email: string;
  role: string;
  email_verified: boolean;
}

export async function signup(orgName: string, email: string, password: string): Promise<{ status: string; email: string }> {
  return api.post<{ status: string; email: string }>("/api/auth/signup", { org_name: orgName, email, password });
}

export async function login(email: string, password: string): Promise<void> {
  const { access_token } = await api.post<{ access_token: string }>("/api/auth/login", { email, password });
  setToken(access_token);
}

export async function verifyEmail(token: string): Promise<void> {
  const { access_token } = await api.post<{ access_token: string }>("/api/auth/verify-email", { token });
  setToken(access_token);
}

export function resendVerification(email: string): Promise<void> {
  return api.post<void>("/api/auth/resend-verification", { email });
}

export function forgotPassword(email: string): Promise<void> {
  return api.post<void>("/api/auth/forgot-password", { email });
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
  const { access_token } = await api.post<{ access_token: string }>("/api/auth/reset-password", { token, new_password: newPassword });
  setToken(access_token);
}

export async function loginWithGoogle(credential: string): Promise<{ isNewUser: boolean }> {
  const { access_token, is_new_user } = await api.post<{ access_token: string; is_new_user: boolean }>("/api/auth/google", { credential });
  setToken(access_token);
  return { isNewUser: is_new_user };
}

export function logout(): void {
  setToken(null);
}

export function me(): Promise<User> {
  return api.get<User>("/api/auth/me");
}
