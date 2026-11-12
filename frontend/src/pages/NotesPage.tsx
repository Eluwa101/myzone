import { Check, CheckCheck, Pencil, Plus, Search, StickyNote, Trash2, X } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { listCustomers } from "../api/customers";
import { createNote, deleteNote, listNotes, updateNote } from "../api/notes";
import { errorMessage } from "../api/errorMessage";
import type { Customer, OrgNote } from "../api/types";
import CardHead from "../components/CardHead";
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
  const [search, setSearch] = useState("");

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

  const filtered = search.trim()
    ? notes.filter((n) => {
        const q = search.trim().toLowerCase();
        return n.title.toLowerCase().includes(q) || n.content.toLowerCase().includes(q) || n.customers.some((c) => c.name.toLowerCase().includes(q));
      })
    : notes;

  return (
    <div>
      <TopBar title="Notes" backTo="/data" />
      <p className="muted small page-note">
        Define your own notes - creditors, VIPs, anything you want to flag - and attach them to one or many customers.
      </p>

      <ErrorText message={error} />

      {adding ? (
        <div className="card form-card">
          <NoteForm
            customers={customers}
            initialCustomerId={preselectCustomerId}
            onCancel={() => setAdding(false)}
            onSaved={() => {
              setAdding(false);
              load();
            }}
          />
        </div>
      ) : (
        <div className="page-actions">
          <button type="button" className="btn-primary" onClick={() => setAdding(true)}>
            <Plus size={15} /> New note
          </button>
          {notes.length > 0 && (
            <div className="search-wrap" style={{ flex: 1, minWidth: 200, maxWidth: 420 }}>
              <Search size={15} className="search-icon" aria-hidden="true" />
              <input
                aria-label="Search notes"
                className="search-input"
                placeholder="Search title, content, customer…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          )}
        </div>
      )}

      {loading ? (
        <Spinner />
      ) : notes.length === 0 ? (
        <p className="muted small page-note">No notes yet.</p>
      ) : filtered.length === 0 ? (
        <p className="muted small page-note">No notes match "{search}".</p>
      ) : (
        <div className="card-grid">
          {filtered.map((n) => (
            <NoteCard key={n.id} note={n} customers={customers} onChanged={load} />
          ))}
        </div>
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
      <div className="card note-card span-all form-card">
        <NoteForm customers={customers} initialNote={note} onCancel={() => setEditing(false)} onSaved={() => { setEditing(false); onChanged(); }} />
      </div>
    );
  }

  return (
    <div className="card note-card">
      <CardHead
        icon={<StickyNote />}
        tone="amber"
        title={note.title}
        subtitle={note.created_by_agent ? "from Assistant" : undefined}
        badges={note.is_pending_review ? <span className="badge badge-lead">Needs review</span> : undefined}
        items={[
          { key: "edit", label: "Edit", icon: <Pencil />, onSelect: () => setEditing(true) },
          { key: "div", divider: true },
          { key: "delete", label: "Delete note", icon: <Trash2 />, danger: true, confirm: "Really delete?", disabled: busy, onSelect: remove },
        ]}
      />
      <button type="button" className="card-body" onClick={() => setEditing(true)}>
        {note.content}
      </button>

      {note.customers.length > 0 && (
        <div className="note-card-customers">
          {note.customers.map((c) => (
            <Link key={c.id} to={`/customers/${c.id}`} className="chip">
              {c.name}
            </Link>
          ))}
        </div>
      )}

      <ErrorText message={error} />
      {note.is_pending_review && (
        <div className="card-actions">
          <button type="button" className="btn-primary" onClick={markReviewed} disabled={busy}>
            <CheckCheck size={14} /> Mark reviewed
          </button>
        </div>
      )}
    </div>
  );
}
