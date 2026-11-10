import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import AuthBrand from "../components/AuthBrand";
import ErrorText from "../components/ErrorText";
import Spinner from "../components/Spinner";
import { errorMessage } from "../api/errorMessage";
import { useAuth } from "../context/AuthContext";

export default function VerifyEmailPage() {
  const { verifyEmail } = useAuth();
  const [params] = useSearchParams();
  const token = params.get("token");
  const [status, setStatus] = useState<"verifying" | "done" | "error">("verifying");
  const [error, setError] = useState<string | null>(null);
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    if (!token) {
      setStatus("error");
      setError("This link is missing its verification token.");
      return;
    }
    verifyEmail(token)
      .then(() => setStatus("done"))
      .catch((err) => {
        setStatus("error");
        setError(errorMessage(err));
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (status === "done") return <Navigate to="/onboarding" replace />;

  return (
    <div className="auth-screen">
      <div className="card auth-card" style={{ textAlign: "center" }}>
        <AuthBrand />
        {status === "verifying" && (
          <div style={{ marginTop: 16 }}>
            <Spinner label="Verifying your email…" />
          </div>
        )}
        {status === "error" && (
          <>
            <ErrorText message={error} />
            <p className="muted" style={{ marginTop: 12 }}>
              <Link to="/login">Back to login</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
