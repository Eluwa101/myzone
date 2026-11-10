import { MailCheck } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import AuthBrand from "../components/AuthBrand";
import { resendVerification } from "../api/auth";
import { errorMessage } from "../api/errorMessage";

export default function CheckEmailPage() {
  const [params] = useSearchParams();
  const email = params.get("email") ?? "";
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onResend() {
    setBusy(true);
    setStatus(null);
    try {
      await resendVerification(email);
      setStatus("Verification email sent - check your inbox.");
    } catch (err) {
      setStatus(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="card auth-card" style={{ textAlign: "center" }}>
        <AuthBrand />
        <MailCheck size={40} className="muted" style={{ margin: "12px auto" }} />
        <h3>Check your email</h3>
        <p className="muted">
          We sent a verification link to {email ? <strong>{email}</strong> : "your email address"}. Click it to activate your
          account.
        </p>
        <button type="button" className="btn-primary" onClick={onResend} disabled={busy || !email} style={{ width: "100%" }}>
          {busy ? "Sending…" : "Resend verification email"}
        </button>
        {status && (
          <p className="muted small" style={{ marginTop: 8 }}>
            {status}
          </p>
        )}
        <p className="muted" style={{ marginTop: 16 }}>
          <Link to="/login">Back to login</Link>
        </p>
      </div>
    </div>
  );
}
