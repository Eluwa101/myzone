import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import AuthBrand from "../components/AuthBrand";
import ErrorText from "../components/ErrorText";
import { forgotPassword } from "../api/auth";
import { errorMessage } from "../api/errorMessage";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await forgotPassword(email);
      setSent(true);
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
        {sent ? (
          <>
            <p className="muted">
              If an account exists for <strong>{email}</strong>, we've sent a link to reset the password. Check your inbox.
            </p>
            <p className="muted">
              <Link to="/login">Back to login</Link>
            </p>
          </>
        ) : (
          <>
            <p className="muted">Enter your account email and we'll send a password reset link.</p>
            <form onSubmit={onSubmit}>
              <label htmlFor="forgot-email">Email</label>
              <input id="forgot-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
              <ErrorText message={error} />
              <button className="btn-primary" type="submit" disabled={busy}>
                {busy ? "Sending…" : "Send reset link"}
              </button>
            </form>
            <p className="muted">
              <Link to="/login">Back to login</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
