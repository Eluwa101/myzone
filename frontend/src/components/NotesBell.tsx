import { Bell } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { getPendingNoteCount, listNotes, updateNote } from "../api/notes";
import type { OrgNote } from "../api/types";

export default function NotesBell() {
  const [count, setCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState<OrgNote[]>([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getPendingNoteCount()
      .then((r) => setCount(r.count))
      .catch(() => {
        /* non-fatal - the app works fine without the badge */
      });
  }, []);

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
      listNotes({ pending: true })
        .then(setNotes)
        .finally(() => setLoading(false));
    }
  }

  async function markReviewed(id: string) {
    await updateNote(id, { is_pending_review: false });
    setNotes((n) => n.filter((note) => note.id !== id));
    setCount((c) => Math.max(0, c - 1));
  }

  if (count === 0 && !open) {
    return (
      <div className="notes-bell-wrap" ref={ref}>
        <button type="button" className="icon-btn btn-ghost" aria-label="Pending notes" title="Pending notes" onClick={toggle}>
          <Bell size={18} />
        </button>
      </div>
    );
  }

  return (
    <div className="notes-bell-wrap" ref={ref}>
      <button type="button" className="icon-btn btn-ghost" aria-label="Pending notes" title="Pending notes" onClick={toggle}>
        <Bell size={18} />
        {count > 0 && <span className="notes-bell-badge">{count}</span>}
      </button>
      {open && (
        <div className="notes-bell-panel">
          <h4 style={{ margin: "0 0 10px" }}>Pending review</h4>
          {loading && <p className="muted small">Loading…</p>}
          {!loading && notes.length === 0 && <p className="muted small">Nothing pending.</p>}
          {notes.map((n) => (
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
                <button type="button" onClick={() => markReviewed(n.id)}>
                  Mark reviewed
                </button>
                <Link to="/notes" onClick={() => setOpen(false)}>
                  Edit
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
