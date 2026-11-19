import { Check, X } from "lucide-react";
import { useState, type FormEvent } from "react";
import { createNote, updateNote } from "../api/notes";
import { errorMessage } from "../api/errorMessage";
import type { Customer, OrgNote } from "../api/types";
import ErrorText from "./ErrorText";

export default function NoteForm({
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
