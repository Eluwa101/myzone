import { FileText, Mail, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { listMessageHistoryPaged, type OutboundMessage } from "../api/messaging";
import ErrorText from "../components/ErrorText";
import InfoTip from "../components/InfoTip";
import Pagination from "../components/Pagination";
import SearchBox from "../components/SearchBox";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";
import { usePagedList } from "../hooks/usePagedList";

const PAGE_SIZE = 20;
const STATUS_LABEL: Record<string, string> = { sent: "Sent", failed: "Failed", skipped: "Skipped", opened: "Opened in WhatsApp" };
const CHANNEL_LABEL: Record<string, string> = { email: "Email", whatsapp: "WhatsApp", sms: "SMS" };

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
  const [status, setStatus] = useState("");
  const [channel, setChannel] = useState("");
  const list = usePagedList<OutboundMessage>({
    fetcher: ({ search, page, pageSize }) => listMessageHistoryPaged({ channel, status, search, page, pageSize }),
    pageSize: PAGE_SIZE,
    filterKey: `${channel}|${status}`,
  });
  const { items: history, loading, error } = list;

  return (
    <div>
      <TopBar title="Messages" backTo="/data" />
      <div className="page-actions">
        <Link to="/messages/compose" className="btn-primary pill-link">
          <Plus size={15} /> Compose message
        </Link>
        <Link to="/messages/templates" className="pill-link">
          <FileText size={15} /> Manage templates
        </Link>
      </div>

      <h2 className="settings-section-heading">
        Recent activity <InfoTip>Every email sent and WhatsApp chat opened with your customers.</InfoTip>
      </h2>
      <div className="toolbar">
        <SearchBox value={list.search} onChange={list.setSearch} label="Search messages" placeholder="Search subject, message, customer…" />
        <select aria-label="Filter by channel" value={channel} onChange={(e) => setChannel(e.target.value)}>
          <option value="">All channels</option>
          <option value="email">Email</option>
          <option value="whatsapp">WhatsApp</option>
        </select>
        <select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="sent">Sent</option>
          <option value="failed">Failed</option>
          <option value="skipped">Skipped</option>
          <option value="opened">Opened in WhatsApp</option>
        </select>
      </div>
      <ErrorText message={error} />
      {loading ? (
        <Spinner />
      ) : history.length === 0 ? (
        <div className="empty-state">
          <Mail size={40} className="empty-state-icon" strokeWidth={1.5} />
          <p>{list.searching || status || channel ? "No messages match." : "No messages yet."}</p>
        </div>
      ) : (
        <div className="card">
          {history.map((m) => (
            <Link key={m.id} to={`/messages/${m.id}`} className="info-row">
              <div className="info-row-text">
                <div className="info-row-label">{m.subject || (m.channel === "email" ? "(no subject)" : `${CHANNEL_LABEL[m.channel] ?? m.channel} message`)}</div>
                <div className="info-row-value muted">
                  {m.customer_name ? `${m.customer_name} · ` : ""}
                  {m.channel !== "email" && m.subject ? `${CHANNEL_LABEL[m.channel] ?? m.channel} · ` : ""}
                  {STATUS_LABEL[m.status] ?? m.status} · {timeAgo(m.created_at)}
                  {m.error ? ` · ${m.error}` : ""}
                </div>
                {m.body_preview && <div className="info-row-value muted small message-preview">{m.body_preview}</div>}
              </div>
            </Link>
          ))}
        </div>
      )}

      {!loading && <Pagination page={list.page} pageSize={PAGE_SIZE} total={list.total} onChange={list.goToPage} />}
    </div>
  );
}
