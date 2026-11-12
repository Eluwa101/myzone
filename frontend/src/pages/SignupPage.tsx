import { useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import AuthBrand from "../components/AuthBrand";
import ErrorText from "../components/ErrorText";
import GoogleSignInButton from "../components/GoogleSignInButton";
import { errorMessage } from "../api/errorMessage";
import { useAuth } from "../context/AuthContext";

export default function SignupPage() {
  const { user, signup, loginWithGoogle } = useAuth();
  const navigate = useNavigate();
  const [orgName, setOrgName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Captured once at mount: redirect only if the user was already logged in
  // when they landed here.
  const alreadyLoggedIn = useRef(!!user);

  if (alreadyLoggedIn.current) return <Navigate to="/customers" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const result = await signup(orgName, email, password);
      navigate(`/check-email?email=${encodeURIComponent(result.email)}`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
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
        <GoogleSignInButton onCredential={onGoogle} text="signup_with" />
        <p className="muted small legal-consent">
          By creating an account you agree to our <Link to="/terms">Terms of Service</Link> and{" "}
          <Link to="/privacy">Privacy Policy</Link>.
        </p>
        <p className="muted">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}
