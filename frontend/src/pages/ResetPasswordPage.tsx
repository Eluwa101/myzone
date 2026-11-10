import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import AuthBrand from "../components/AuthBrand";
import ErrorText from "../components/ErrorText";
import { errorMessage } from "../api/errorMessage";
import { useAuth } from "../context/AuthContext";

export default function ResetPasswordPage() {
  const { resetPassword } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get("token");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!token) return <Navigate to="/forgot-password" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await resetPassword(token!, password);
      navigate("/customers");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="card auth-card">
        <AuthBrand />
        <p className="muted">Choose a new password.</p>
        <form onSubmit={onSubmit}>
          <label htmlFor="reset-password">New password</label>
          <input
            id="reset-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoFocus
          />
          <ErrorText message={error} />
          <button className="btn-primary" type="submit" disabled={busy}>
            {busy ? "Saving…" : "Reset password"}
          </button>
        </form>
        <p className="muted">
          <Link to="/login">Back to login</Link>
        </p>
      </div>
    </div>
  );
}
