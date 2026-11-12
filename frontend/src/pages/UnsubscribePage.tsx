import { MailCheck, MailX } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { errorMessage } from "../api/errorMessage";

interface UnsubscribeStatus {
  business_name: string;
  unsubscribed: boolean;
}

/** Where the "Unsubscribe" link at the bottom of a customer email lands.
 * Unsubscribes straight away (from script, so link-scanning bots that
 * only fetch the page don't trigger it), with an undo. */
export default function UnsubscribePage() {
  const { token = "" } = useParams();
  const [status, setStatus] = useState<UnsubscribeStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return; // StrictMode runs effects twice in dev
    started.current = true;
    api
      .post<UnsubscribeStatus>(`/api/public/unsubscribe/${token}`, {})
      .then(setStatus)
      .catch((err) => setError(errorMessage(err)));
  }, [token]);

  async function toggle() {
    if (!status) return;
    setBusy(true);
    setError(null);
    try {
      const path = status.unsubscribed ? `/api/public/unsubscribe/${token}/resubscribe` : `/api/public/unsubscribe/${token}`;
      setStatus(await api.post<UnsubscribeStatus>(path, {}));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="card auth-card unsubscribe-card">
        {error ? (
          <>
            <h1>Something went wrong</h1>
            <p className="muted">{error}</p>
          </>
        ) : !status ? (
          <p className="muted">Unsubscribing…</p>
        ) : status.unsubscribed ? (
          <>
            <MailX size={36} className="unsubscribe-icon" aria-hidden="true" />
            <h1>You're unsubscribed</h1>
            <p className="muted">You won't get any more emails from {status.business_name} sent through MyShop.</p>
            <button type="button" onClick={toggle} disabled={busy}>
              {busy ? "One moment…" : "Unsubscribed by mistake? Resubscribe"}
            </button>
          </>
        ) : (
          <>
            <MailCheck size={36} className="unsubscribe-icon" aria-hidden="true" />
            <h1>You're subscribed</h1>
            <p className="muted">You'll keep getting emails from {status.business_name}.</p>
            <button type="button" className="btn-danger" onClick={toggle} disabled={busy}>
              {busy ? "One moment…" : "Unsubscribe"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
