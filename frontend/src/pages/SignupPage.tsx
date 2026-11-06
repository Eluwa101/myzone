import { useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import AuthBrand from "../components/AuthBrand";
import ErrorText from "../components/ErrorText";
import { errorMessage } from "../api/errorMessage";
import { useAuth } from "../context/AuthContext";

export default function SignupPage() {
  const { user, signup } = useAuth();
  const navigate = useNavigate();
  const [orgName, setOrgName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Captured once at mount: redirect only if the user was already logged in
  // when they landed here. signup() sets `user` before navigate("/onboarding")
  // runs below, and re-checking `user` on every render would send them to
  // /customers first, racing out the onboarding redirect.
  const alreadyLoggedIn = useRef(!!user);

  if (alreadyLoggedIn.current) return <Navigate to="/customers" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await signup(orgName, email, password);
      navigate("/onboarding");
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
        <p className="muted">Set up your business account.</p>
        <form onSubmit={onSubmit}>
          <label htmlFor="signup-org">Business name</label>
          <input id="signup-org" value={orgName} onChange={(e) => setOrgName(e.target.value)} required autoFocus />
          <label htmlFor="signup-email">Email</label>
          <input id="signup-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <label htmlFor="signup-password">Password</label>
          <input id="signup-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
          <ErrorText message={error} />
          <button className="btn-primary" type="submit" disabled={busy}>
            {busy ? "Creating account…" : "Create account"}
          </button>
        </form>
        <p className="muted">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}
