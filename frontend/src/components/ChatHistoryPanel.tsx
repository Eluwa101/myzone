import { Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { deleteThread, listThreads, type ChatThread } from "../api/agent";

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}

export default function ChatHistoryPanel({
  onSelect,
  onClose,
}: {
  onSelect: (threadId: string) => void;
  onClose: () => void;
}) {
  const [threads, setThreads] = useState<ChatThread[] | null>(null);
  const [armedDelete, setArmedDelete] = useState<string | null>(null);

  function load() {
    listThreads().then(setThreads).catch(() => setThreads([]));
  }

  useEffect(load, []);

  async function onDelete(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    if (armedDelete !== id) {
      setArmedDelete(id);
      return;
    }
    setArmedDelete(null);
    await deleteThread(id);
    load();
  }

  return (
    <div className="history-overlay" onClick={onClose}>
      <div className="card history-panel" onClick={(e) => e.stopPropagation()}>
        <div className="row-between" style={{ border: "none", paddingBottom: 6 }}>
          <h3 style={{ margin: 0 }}>Past chats</h3>
          <button className="icon-btn btn-ghost" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>
        {threads === null ? (
          <p className="muted small">Loading…</p>
        ) : threads.length === 0 ? (
          <p className="muted small">No past chats yet.</p>
        ) : (
          <ul className="history-list">
            {threads.map((t) => (
              <li key={t.id} className="history-item" onClick={() => onSelect(t.id)}>
                <div>
                  <div className="history-title">{t.title}</div>
                  <div className="muted small">{relativeTime(t.updated_at)}</div>
                </div>
                <button
                  className="icon-btn btn-danger"
                  onClick={(e) => onDelete(e, t.id)}
                  aria-label={armedDelete === t.id ? "Confirm delete" : "Delete chat"}
                >
                  <Trash2 size={14} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
