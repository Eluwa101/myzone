import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import * as authApi from "../api/auth";
import { getToken } from "../api/client";
import type { User } from "../api/auth";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (orgName: string, email: string, password: string) => Promise<{ status: string; email: string }>;
  loginWithGoogle: (credential: string) => Promise<{ isNewUser: boolean }>;
  verifyEmail: (token: string) => Promise<void>;
  resetPassword: (token: string, newPassword: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await authApi.me());
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function login(email: string, password: string) {
    await authApi.login(email, password);
    await refresh();
  }

  async function signup(orgName: string, email: string, password: string) {
    // signup no longer logs the caller in directly - the account must be
    // verified by email first (see routes /verify-email, /check-email)
    return authApi.signup(orgName, email, password);
  }

  async function loginWithGoogle(credential: string) {
    const result = await authApi.loginWithGoogle(credential);
    await refresh();
    return result;
  }

  async function verifyEmail(token: string) {
    await authApi.verifyEmail(token);
    await refresh();
  }

  async function resetPassword(token: string, newPassword: string) {
    await authApi.resetPassword(token, newPassword);
    await refresh();
  }

  function logout() {
    authApi.logout();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, signup, loginWithGoogle, verifyEmail, resetPassword, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
