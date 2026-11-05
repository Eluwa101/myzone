import { useState } from "react";
import { Link } from "react-router-dom";
import { confirmPending, rejectPending } from "../api/agent";
import { errorMessage } from "../api/errorMessage";
import type { PendingAction } from "../api/types";

function referencedCustomerLinks(action: PendingAction): { id: string; label: string }[] {
  const payload = action.payload as Record<string, unknown>;
  if (action.tool_name === "delete_customer" && typeof payload.customer_id === "string") {
    return [{ id: payload.customer_id, label: "View customer" }];
  }
  if (action.tool_name === "merge_customers") {
    const links: { id: string; label: string }[] = [];
    if (typeof payload.keep_id === "string") links.push({ id: payload.keep_id, label: "View customer to keep" });
    if (typeof payload.merge_id === "string") links.push({ id: payload.merge_id, label: "View duplicate" });
    return links;
  }
  return [];
}

export default function PendingActionCard({ action, onResolved }: { action: PendingAction; onResolved: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const customerLinks = referencedCustomerLinks(action);

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
      {customerLinks.length > 0 && (
        <div className="row" style={{ marginBottom: 8 }}>
          {customerLinks.map((l) => (
            <Link key={l.id} to={`/customers/${l.id}`} className="chip">
              {l.label}
            </Link>
          ))}
        </div>
      )}
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
