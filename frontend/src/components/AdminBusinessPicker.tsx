import { Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { enterBusiness, leaveBusiness, listAdminOrgs, type AdminOrg } from "../api/admin";
import { errorMessage } from "../api/errorMessage";
import ErrorText from "./ErrorText";
import Spinner from "./Spinner";

/** The admin's list of every business, to open one and help. */
export default function AdminBusinessPicker({ currentOrgId, onClose }: { currentOrgId: string; onClose: () => void }) {
  const [orgs, setOrgs] = useState<AdminOrg[] | null>(null);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAdminOrgs()
      .then(setOrgs)
      .catch((err) => setError(errorMessage(err)));
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function open(org: AdminOrg) {
    setBusy(org.id);
    setError(null);
    try {
      if (org.is_home) await leaveBusiness();
      else await enterBusiness(org.id);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(null);
    }
  }

  const q = query.trim().toLowerCase();
  const shown = (orgs ?? []).filter((o) => !q || o.name.toLowerCase().includes(q) || (o.owner_email ?? "").toLowerCase().includes(q));

  return (
    <div className="history-overlay" onClick={onClose}>
      <div className="card admin-picker" role="dialog" aria-label="Open a business as admin" onClick={(e) => e.stopPropagation()}>
        <div className="row-between" style={{ borderBottom: "none" }}>
          <h3 style={{ margin: 0 }}>Open a business</h3>
          <button type="button" className="icon-btn btn-ghost" aria-label="Close" onClick={onClose}>
            <X size={16} />
          </button>
        </div>
        <p className="muted small">
          You'll have full access for 2 hours to help them. They're notified in their bell, and every change is logged.
        </p>
        <div className="search-wrap">
          <Search size={16} className="search-icon" aria-hidden="true" />
          <input className="search-input" aria-label="Search businesses" placeholder="Search by name or owner email…" value={query} onChange={(e) => setQuery(e.target.value)} autoFocus />
        </div>
        <ErrorText message={error} />
        {orgs === null ? (
          <Spinner />
        ) : (
          <div className="admin-picker-list">
            {shown.map((o) => {
              const here = o.id === currentOrgId;
              return (
                <button key={o.id} type="button" className="admin-picker-item" onClick={() => open(o)} disabled={here || busy !== null}>
                  <span>
                    <b>{o.name}</b>
                    {o.is_home && <span className="admin-picker-tag">Your business</span>}
                    {o.closing && <span className="admin-picker-tag admin-picker-tag-warn">Closing</span>}
                    {here && <span className="admin-picker-tag">You're here</span>}
                    <span className="muted small admin-picker-meta">
                      {o.owner_email ?? "no owner"} · {o.customers} customer{o.customers === 1 ? "" : "s"}
                    </span>
                  </span>
                  <span className="small">{busy === o.id ? "Opening…" : o.is_home ? "Back" : "Open"}</span>
                </button>
              );
            })}
            {shown.length === 0 && <p className="muted small">No businesses match.</p>}
          </div>
        )}
      </div>
    </div>
  );
}
