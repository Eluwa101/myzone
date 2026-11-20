import { CheckCheck, Pencil, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { listCustomers } from "../api/customers";
import { deleteNote, getNote, updateNote } from "../api/notes";
import { errorMessage } from "../api/errorMessage";
import type { Customer, OrgNote } from "../api/types";
import CardMenu from "../components/CardMenu";
import ErrorText from "../components/ErrorText";
import NoteForm from "../components/NoteForm";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";

/** One note in full - the page the clipped "View full" link on the Notes list opens. */
export default function NoteDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [note, setNote] = useState<OrgNote | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    getNote(id)
      .then(setNote)
      .catch((err) => setError(errorMessage(err)));
  }

  useEffect(load, [id]);
  useEffect(() => {
    if (editing && customers.length === 0) listCustomers({ pageSize: 200 }).then((c) => setCustomers(c.items)).catch(() => {});
  }, [editing, customers.length]);

  async function markReviewed() {
    setBusy(true);
    try {
      await updateNote(id, { is_pending_review: false });
      load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    try {
      await deleteNote(id);
      navigate("/notes", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <div>
      <TopBar title="Note" backTo="/notes" />
      <ErrorText message={error} />
      {!note ? (
        error ? null : <Spinner />
      ) : editing ? (
        <div className="card form-card">
          <NoteForm
            customers={customers}
            initialNote={note}
            onCancel={() => setEditing(false)}
            onSaved={() => {
              setEditing(false);
              load();
            }}
          />
        </div>
      ) : (
        <div className="card">
          <div className="row-between">
            <h2 style={{ margin: 0 }}>{note.title}</h2>
            <div className="row" style={{ gap: 6 }}>
              {note.is_pending_review && <span className="badge badge-lead">Needs review</span>}
              <CardMenu
                items={[
                  { key: "edit", label: "Edit", icon: <Pencil />, disabled: busy, onSelect: () => setEditing(true) },
                  { key: "div", divider: true },
                  { key: "delete", label: "Delete note", icon: <Trash2 />, danger: true, confirm: "Really delete?", disabled: busy, onSelect: remove },
                ]}
              />
            </div>
          </div>
          <p className="muted small">
            {note.created_by_agent ? "From Assistant · " : ""}
            {new Date(note.created_at).toLocaleString()}
          </p>
          <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{note.content}</p>

          {note.customers.length > 0 && (
            <div className="note-card-customers">
              {note.customers.map((c) => (
                <Link key={c.id} to={`/customers/${c.id}`} className="chip">
                  {c.name}
                </Link>
              ))}
            </div>
          )}

          {note.is_pending_review && (
            <div className="card-actions" style={{ marginTop: 12 }}>
              <button type="button" className="btn-primary" onClick={markReviewed} disabled={busy}>
                <CheckCheck size={14} /> Mark reviewed
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
