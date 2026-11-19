import { CheckCheck, Pencil, Plus, StickyNote, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { listCustomers } from "../api/customers";
import { deleteNote, listNotesPaged, updateNote } from "../api/notes";
import { errorMessage } from "../api/errorMessage";
import type { Customer, OrgNote } from "../api/types";
import CardHead from "../components/CardHead";
import ClampText from "../components/ClampText";
import ErrorText from "../components/ErrorText";
import NoteForm from "../components/NoteForm";
import Pagination from "../components/Pagination";
import SearchBox from "../components/SearchBox";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";
import { usePagedList } from "../hooks/usePagedList";

const PAGE_SIZE = 20;

export default function NotesPage() {
  const [searchParams] = useSearchParams();
  const preselectCustomerId = searchParams.get("customer_id");

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [adding, setAdding] = useState(!!preselectCustomerId);

  const list = usePagedList<OrgNote>({
    fetcher: ({ search, page, pageSize }) => listNotesPaged({ search, page, pageSize }),
    pageSize: PAGE_SIZE,
  });
  const { items: notes, loading, error } = list;

  // only the add/edit form needs the customer list, so it isn't part of every page load
  useEffect(() => {
    listCustomers({ pageSize: 200 }).then((c) => setCustomers(c.items)).catch(() => {});
  }, []);
  const load = list.reload;

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
          <SearchBox value={list.search} onChange={list.setSearch} label="Search notes" placeholder="Search title, content, customer…" />
        </div>
      )}

      {loading ? (
        <Spinner />
      ) : notes.length === 0 ? (
        <p className="muted small page-note">{list.searching ? "No notes match that search." : "No notes yet."}</p>
      ) : (
        <div className="card-grid">
          {notes.map((n) => (
            <NoteCard key={n.id} note={n} customers={customers} onChanged={load} />
          ))}
        </div>
      )}

      {!loading && <Pagination page={list.page} pageSize={PAGE_SIZE} total={list.total} onChange={list.goToPage} />}
    </div>
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
      <div className="card-body">
        <ClampText text={note.content} to={`/notes/${note.id}`} />
      </div>

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
