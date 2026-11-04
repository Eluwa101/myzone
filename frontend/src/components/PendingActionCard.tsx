import { useState } from "react";
import { confirmPending, rejectPending } from "../api/agent";
import { errorMessage } from "../api/errorMessage";
import type { PendingAction } from "../api/types";

export default function PendingActionCard({ action, onResolved }: { action: PendingAction; onResolved: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await confirmPending(action.id);
      onResolved();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  async function reject() {
    setBusy(true);
    setError(null);
    try {
      await rejectPending(action.id);
      onResolved();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <div className="card pending-card">
      <div className="pending-card-label">Needs your confirmation</div>
      <p>{action.description}</p>
      <div className="row">
        <button className="btn-primary" onClick={confirm} disabled={busy}>
          Confirm
        </button>
        <button className="btn-danger" onClick={reject} disabled={busy}>
          Discard
        </button>
      </div>
      {error && <p className="error-text small">{error}</p>}
    </div>
  );
}
