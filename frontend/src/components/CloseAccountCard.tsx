import { AlertTriangle } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { cancelClosure, formatClosureDate, getClosure, requestClosure, type ClosureStatus } from "../api/account";
import { errorMessage } from "../api/errorMessage";
import ErrorText from "./ErrorText";

/** Settings "danger zone": close the account (after a read-only grace
 * period everything is deleted) or cancel a pending closure. */
export default function CloseAccountCard() {
  const [status, setStatus] = useState<ClosureStatus | null>(null);
  const [open, setOpen] = useState(false);
  const [confirmName, setConfirmName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getClosure()
      .then(setStatus)
      .catch((err) => setError(errorMessage(err)));
  }, []);

  async function onClose(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setStatus(await requestClosure(confirmName));
      setOpen(false);
      setConfirmName("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function onCancel() {
    setBusy(true);
    setError(null);
    try {
      setStatus(await cancelClosure());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (!status) {
    return (
      <div className="card danger-card">
        <h3>Close account</h3>
        <ErrorText message={error} />
      </div>
    );
  }

  if (status.closing) {
    return (
      <div className="card danger-card">
        <h3>
          <AlertTriangle size={15} className="h3-icon" /> This account is closing
        </h3>
        <p className="small">
          On <b>{formatClosureDate(status.scheduled_for)}</b>, everything for {status.business_name} will be permanently deleted.
          {status.requested_by && <> Requested by {status.requested_by} on {formatClosureDate(status.requested_at)}.</>}
        </p>
        <p className="muted small">
          Until then the account is read-only. You can still <Link to="/data">export your customers</Link>.
        </p>
        <ErrorText message={error} />
        <button type="button" className="btn-primary" onClick={onCancel} disabled={busy}>
          {busy ? "Cancelling…" : "Cancel closure and keep the account"}
        </button>
      </div>
    );
  }

  return (
    <div className="card danger-card">
      <h3>Close account</h3>
      <p className="muted small">
        Permanently delete {status.business_name} and everything in it: customers, sales, orders, notes, messages, templates, segments,
        forms, API keys and assistant chats. You'll have {status.grace_days} days to export your data or change your mind first.
      </p>
      {!open ? (
        <button type="button" className="btn-danger" onClick={() => setOpen(true)}>
          Close account…
        </button>
      ) : (
        <form onSubmit={onClose}>
          <ul className="small close-account-steps">
            <li>The account becomes read-only straight away - nothing can be added or changed, and public forms stop taking entries.</li>
            <li>Everyone on the account gets an email with the deletion date.</li>
            <li>
              On day {status.grace_days} everything is deleted for good. It can't be recovered after that. Any owner can cancel before
              then.
            </li>
          </ul>
          <label htmlFor="close-confirm">
            Type <b>{status.business_name}</b> to confirm
          </label>
          <input id="close-confirm" value={confirmName} onChange={(e) => setConfirmName(e.target.value)} autoComplete="off" />
          <ErrorText message={error} />
          <div className="row" style={{ marginTop: 10 }}>
            <button type="submit" className="btn-danger" disabled={busy || !confirmName.trim()}>
              {busy ? "Closing…" : "Close account"}
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                setConfirmName("");
                setError(null);
              }}
              disabled={busy}
            >
              Keep my account
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
