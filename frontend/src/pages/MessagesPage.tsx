import { FileText, Mail, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../api/errorMessage";
import { listMessageHistory, type OutboundMessage } from "../api/messaging";
import ErrorText from "../components/ErrorText";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";

const STATUS_LABEL: Record<string, string> = { sent: "Sent", failed: "Failed", skipped: "Skipped" };

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export default function MessagesPage() {
  const [history, setHistory] = useState<OutboundMessage[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listMessageHistory()
      .then(setHistory)
      .catch((err) => setError(errorMessage(err)));
  }, []);

  return (
    <div>
      <TopBar title="Messages" backTo="/data" />
      <p className="muted small page-note">Email customers directly, with merge tags filled in per recipient.</p>

      <div className="card">
        <div className="row">
          <Link to="/messages/compose" className="btn-primary">
            <Plus size={15} /> Compose email
          </Link>
          <Link to="/messages/templates">
            <FileText size={15} /> Manage templates
          </Link>
        </div>
      </div>

      <h2 className="settings-section-heading">Recent activity</h2>
      <ErrorText message={error} />
      {history === null ? (
        <Spinner />
      ) : history.length === 0 ? (
        <div className="empty-state">
          <Mail size={40} className="empty-state-icon" strokeWidth={1.5} />
          <p>No emails sent yet.</p>
        </div>
      ) : (
        <div className="card">
          {history.map((m) => (
            <Link key={m.id} to={`/customers/${m.customer_id}`} className="info-row">
              <div className="info-row-text">
                <div className="info-row-label">{m.subject || "(no subject)"}</div>
                <div className="info-row-value muted">
                  {STATUS_LABEL[m.status] ?? m.status} · {timeAgo(m.created_at)}
                  {m.error ? ` · ${m.error}` : ""}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
