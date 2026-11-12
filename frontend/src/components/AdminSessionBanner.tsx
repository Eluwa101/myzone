import { ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { currentAdminSession, leaveBusiness } from "../api/admin";

/** Red bar across every screen while an admin is inside someone else's
 * business, so it's never mistaken for their own. Leaves automatically
 * when the session runs out. */
export default function AdminSessionBanner() {
  const [session] = useState(currentAdminSession);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    if (!session) return;
    const msLeft = new Date(session.expires_at).getTime() - Date.now();
    const handle = setTimeout(() => leaveBusiness(), Math.max(0, msLeft));
    return () => clearTimeout(handle);
  }, [session]);

  if (!session) return null;
  const until = new Date(session.expires_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return (
    <div className="admin-session-banner" role="status">
      <ShieldAlert size={16} aria-hidden="true" />
      <span>
        <b>Admin:</b> you're in <b>{session.org_name}</b>'s account. Changes are real and logged, and they've been notified. Ends at {until}.
      </span>
      <button
        type="button"
        onClick={() => {
          setLeaving(true);
          leaveBusiness();
        }}
        disabled={leaving}
      >
        {leaving ? "Leaving…" : "Back to my account"}
      </button>
    </div>
  );
}
