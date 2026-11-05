import { Check, ChevronRight, Plus, Trash2, X } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { listCustomers } from "../api/customers";
import { createNote, deleteNote, listNotes, updateNote } from "../api/notes";
import { errorMessage } from "../api/errorMessage";
import type { Customer, OrgNote } from "../api/types";
import ErrorText from "../components/ErrorText";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";

export default function NotesPage() {
  const [searchParams] = useSearchParams();
  const preselectCustomerId = searchParams.get("customer_id");

  const [notes, setNotes] = useState<OrgNote[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(!!preselectCustomerId);

  function load() {
    setLoading(true);
    setError(null);
    Promise.all([listNotes(), listCustomers({ pageSize: 200 })])
      .then(([n, c]) => {
        setNotes(n);
        setCustomers(c.items);
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  return (
    <div>
      <TopBar title="Notes" />
      <p className="muted small page-note">
        Define your own notes - creditors, VIPs, anything you want to flag - and attach them to one or many customers.
      </p>

      <ErrorText message={error} />

      <div className="card">
        {adding ? (
          <NoteForm
            customers={customers}
            initialCustomerId={preselectCustomerId}
            onCancel={() => setAdding(false)}
            onSaved={() => {
              setAdding(false);
              load();
            }}
          />
        ) : (
          <button type="button" className="icon-btn btn-ghost" onClick={() => setAdding(true)}>
            <Plus size={15} /> New note
          </button>
        )}
      </div>

      {loading ? (
        <Spinner />
      ) : notes.length === 0 ? (
        <p className="muted small page-note">No notes yet.</p>
      ) : (
        notes.map((n) => <NoteCard key={n.id} note={n} customers={customers} onChanged={load} />)
      )}
    </div>
  );
}

function NoteForm({
  customers,
  initialCustomerId,
  initialNote,
  onCancel,
  onSaved,
}: {
  customers: Customer[];
  initialCustomerId?: string | null;
  initialNote?: OrgNote;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [title, setTitle] = useState(initialNote?.title ?? "");
  const [content, setContent] = useState(initialNote?.content ?? "");
  const [selected, setSelected] = useState<Set<string>>(
    new Set(initialNote ? initialNote.customers.map((c) => c.id) : initialCustomerId ? [initialCustomerId] : [])
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!title.trim() || !content.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const payload = { title: title.trim(), content: content.trim(), customer_ids: Array.from(selected) };
      if (initialNote) await updateNote(initialNote.id, payload);
      else await createNote(payload);
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="info-row-editing" onSubmit={onSubmit}>
      <label htmlFor="note-title">Title</label>
      <input id="note-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Creditors" autoFocus />
      <label htmlFor="note-content">Note</label>
      <textarea id="note-content" rows={3} value={content} onChange={(e) => setContent(e.target.value)} />
      <label>Attach to customer(s)</label>
      <div className="note-customer-checklist">
        {customers.length === 0 && <p className="muted small">No customers yet.</p>}
        {customers.map((c) => (
          <label key={c.id}>
            <input type="checkbox" checked={selected.has(c.id)} onChange={() => toggle(c.id)} />
            {c.name}
          </label>
        ))}
      </div>
      <ErrorText message={error} />
      <div className="row" style={{ marginTop: 10 }}>
        <button type="submit" className="btn-primary" disabled={busy}>
          <Check size={15} /> Save
        </button>
        <button type="button" onClick={onCancel} disabled={busy}>
          <X size={15} /> Cancel
        </button>
      </div>
    </form>
  );
}

function NoteCard({ note, customers, onChanged }: { note: OrgNote; customers: Customer[]; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [armedDelete, setArmedDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function markReviewed() {
    setBusy(true);
    setError(null);
    try {
      await updateNote(note.id, { is_pending_review: false });
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!armedDelete) {
      setArmedDelete(true);
      return;
    }
    setBusy(true);
    try {
      await deleteNote(note.id);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  if (editing) {
    return (
      <div className="card note-card">
        <NoteForm customers={customers} initialNote={note} onCancel={() => setEditing(false)} onSaved={() => { setEditing(false); onChanged(); }} />
      </div>
    );
  }

  return (
    <div className="card note-card">
      <button type="button" className="info-row" onClick={() => setEditing(true)} style={{ borderBottom: "none", padding: 0 }}>
        <div className="info-row-text">
          <div className="row" style={{ marginBottom: 4 }}>
            <span className="info-row-label" style={{ marginBottom: 0, fontWeight: 600, fontSize: 14, color: "var(--text)" }}>
              {note.title}
            </span>
            {note.is_pending_review && <span className="badge badge-lead">Needs review</span>}
            {note.created_by_agent && <span className="muted small">from Assistant</span>}
          </div>
          <div className="info-row-value muted" style={{ fontWeight: 400 }}>
            {note.content}
          </div>
        </div>
        <ChevronRight size={16} className="muted" />
      </button>

      {note.customers.length > 0 && (
        <div className="note-card-customers">
          {note.customers.map((c) => (
            <span key={c.id} className="chip">
              {c.name}
            </span>
          ))}
        </div>
      )}

      <ErrorText message={error} />
      <div className="row" style={{ marginTop: 10 }}>
        {note.is_pending_review && (
          <button type="button" className="btn-primary" onClick={markReviewed} disabled={busy}>
            Mark reviewed
          </button>
        )}
        <button type="button" className="btn-danger" onClick={remove} disabled={busy} style={{ marginLeft: "auto" }}>
          <Trash2 size={15} /> {armedDelete ? "Confirm?" : "Delete"}
        </button>
      </div>
    </div>
  );
}
