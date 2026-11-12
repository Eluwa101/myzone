import { AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CLOSURE_CHANGED_EVENT, formatClosureDate, getClosure, type ClosureStatus } from "../api/account";

/** Shown on every screen while the account is waiting to be deleted, so
 * nobody is surprised that changes aren't being saved. */
export default function ClosureBanner() {
  const [status, setStatus] = useState<ClosureStatus | null>(null);

  useEffect(() => {
    function load() {
      getClosure()
        .then(setStatus)
        .catch(() => setStatus(null));
    }
    load();
    window.addEventListener(CLOSURE_CHANGED_EVENT, load);
    return () => window.removeEventListener(CLOSURE_CHANGED_EVENT, load);
  }, []);

  if (!status?.closing) return null;
  return (
    <div className="closure-banner" role="status">
      <AlertTriangle size={15} aria-hidden="true" />
      <span>
        This account will be deleted on <b>{formatClosureDate(status.scheduled_for)}</b> and is read-only until then.{" "}
        <Link to="/settings">Cancel the closure</Link>
      </span>
    </div>
  );
}
