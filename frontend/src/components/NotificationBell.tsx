import {
  AlertTriangle,
  Bell,
  ClipboardList,
  Package,
  Plug,
  StickyNote,
  Upload,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  getUnreadNotificationCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type Notification,
} from "../api/notifications";
import { getPendingNoteCount, listNotes, updateNote } from "../api/notes";
import type { OrgNote } from "../api/types";

function iconFor(type: string) {
  if (type.startsWith("order.")) return Package;
  if (type.startsWith("webhook.")) return Plug;
  if (type.startsWith("import.")) return Upload;
  if (type === "form.submission") return ClipboardList;
  if (type === "agent.unavailable") return AlertTriangle;
  if (type === "note.pending_review") return StickyNote;
  return Bell;
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export default function NotificationBell() {
  const navigate = useNavigate();
  const [pendingNoteCount, setPendingNoteCount] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [pendingNotes, setPendingNotes] = useState<OrgNote[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const ref = useRef<HTMLDivElement>(null);

  function refreshCounts() {
    getPendingNoteCount()
      .then((r) => setPendingNoteCount(r.count))
      .catch(() => {});
    getUnreadNotificationCount()
      .then((r) => setUnreadCount(r.count))
      .catch(() => {});
  }

  useEffect(refreshCounts, []);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next) {
      setLoading(true);
      Promise.all([listNotes({ pending: true }), listNotifications()])
        .then(([notes, notifs]) => {
          setPendingNotes(notes);
          setNotifications(notifs);
        })
        .catch(() => {
          /* non-fatal - the dropdown just shows nothing rather than crashing */
        })
        .finally(() => setLoading(false));
    }
  }

  async function markNoteReviewed(id: string) {
    await updateNote(id, { is_pending_review: false });
    setPendingNotes((n) => n.filter((note) => note.id !== id));
    setPendingNoteCount((c) => Math.max(0, c - 1));
  }

  async function onNotificationClick(n: Notification) {
    if (!n.read) {
      await markNotificationRead(n.id);
      setNotifications((list) => list.map((x) => (x.id === n.id ? { ...x, read: true } : x)));
      setUnreadCount((c) => Math.max(0, c - 1));
    }
    if (n.link) {
      setOpen(false);
      navigate(n.link);
    }
  }

  async function onMarkAllRead() {
    await markAllNotificationsRead();
    setNotifications((list) => list.map((n) => ({ ...n, read: true })));
    setUnreadCount(0);
  }

  const totalBadge = pendingNoteCount + unreadCount;

  return (
    <div className="notes-bell-wrap" ref={ref}>
      <button type="button" className="icon-btn btn-ghost" aria-label="Notifications" title="Notifications" onClick={toggle}>
        <Bell size={18} />
        {totalBadge > 0 && <span className="notes-bell-badge">{totalBadge > 99 ? "99+" : totalBadge}</span>}
      </button>
      {open && (
        <div className="notes-bell-panel">
          {loading && <p className="muted small">Loading…</p>}

          {!loading && pendingNotes.length > 0 && (
            <>
              <h4 style={{ margin: "0 0 10px" }}>Pending review</h4>
              {pendingNotes.map((n) => (
                <div key={n.id} className="notes-bell-item">
                  <div className="info-row-label">{n.title}</div>
                  <p className="small" style={{ margin: "2px 0 4px" }}>
                    {n.content}
                  </p>
                  <div className="muted small">
                    {n.customers.length === 0 ? (
                      "Not attached to a customer"
                    ) : (
                      n.customers.map((c, i) => (
                        <span key={c.id}>
                          {i > 0 && ", "}
                          <Link to={`/customers/${c.id}`} onClick={() => setOpen(false)}>
                            {c.name}
                          </Link>
                        </span>
                      ))
                    )}
                  </div>
                  <div className="row" style={{ marginTop: 8 }}>
                    <button type="button" onClick={() => markNoteReviewed(n.id)}>
                      Mark reviewed
                    </button>
                    <Link to="/notes" onClick={() => setOpen(false)}>
                      Edit
                    </Link>
                  </div>
                </div>
              ))}
            </>
          )}

          {!loading && (
            <>
              <div className="row-between" style={{ borderBottom: "none", margin: pendingNotes.length > 0 ? "14px 0 4px" : "0 0 4px" }}>
                <h4 style={{ margin: 0 }}>Notifications</h4>
                {unreadCount > 0 && (
                  <button type="button" className="icon-btn btn-ghost small" onClick={onMarkAllRead}>
                    Mark all read
                  </button>
                )}
              </div>
              {notifications.length === 0 ? (
                <p className="muted small">Nothing yet.</p>
              ) : (
                notifications.map((n) => {
                  const Icon = iconFor(n.type);
                  return (
                    <button
                      key={n.id}
                      type="button"
                      className={`notification-item${n.read ? "" : " notification-item-unread"}`}
                      onClick={() => onNotificationClick(n)}
                    >
                      <Icon size={15} className="notification-item-icon" />
                      <div className="notification-item-text">
                        <div className="small">{n.title}</div>
                        <div className="muted small">{timeAgo(n.created_at)}</div>
                      </div>
                      {!n.read && <span className="notification-item-dot" />}
                    </button>
                  );
                })
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
