import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import AuthBrand from "../components/AuthBrand";
import ErrorText from "../components/ErrorText";
import GoogleSignInButton from "../components/GoogleSignInButton";
import { resendVerification } from "../api/auth";
import { ApiError } from "../api/client";
import { errorMessage } from "../api/errorMessage";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { user, login, loginWithGoogle } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [needsVerification, setNeedsVerification] = useState(false);
  const [resendStatus, setResendStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/customers" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setNeedsVerification(false);
    setResendStatus(null);
    setBusy(true);
    try {
      await login(email, password);
      navigate("/customers");
    } catch (err) {
      if (err instanceof ApiError && err.status === 403 && (err.detail as { code?: string } | undefined)?.code === "email_not_verified") {
        setNeedsVerification(true);
      }
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function onResend() {
    setResendStatus("Sending…");
    try {
      await resendVerification(email);
      setResendStatus("Verification email sent - check your inbox.");
    } catch (err) {
      setResendStatus(errorMessage(err));
    }
  }

  async function onGoogle(credential: string) {
    setError(null);
    try {
      const { isNewUser } = await loginWithGoogle(credential);
      navigate(isNewUser ? "/onboarding" : "/customers");
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="auth-screen">
      <div className="card auth-card">
        <AuthBrand />
        <p className="muted">Log in to your business account.</p>
        <form onSubmit={onSubmit}>
          <label htmlFor="login-email">Email</label>
          <input id="login-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
          <label htmlFor="login-password">Password</label>
          <input id="login-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          <ErrorText message={error} />
          {needsVerification && (
            <p className="small" style={{ marginTop: 4 }}>
              <button type="button" className="btn-ghost small" onClick={onResend} style={{ padding: 0 }}>
                Resend verification email
              </button>
            </p>
          )}
          {resendStatus && <p className="muted small">{resendStatus}</p>}
          <button className="btn-primary" type="submit" disabled={busy}>
            {busy ? "Logging in…" : "Log in"}
          </button>
          <div className="auth-links">
            <Link to="/forgot-password">Forgot password?</Link>
          </div>
        </form>
        <GoogleSignInButton onCredential={onGoogle} text="signin_with" />
        <p className="muted">
          No account yet? <Link to="/signup">Create one</Link>
        </p>
      </div>
    </div>
  );
}
