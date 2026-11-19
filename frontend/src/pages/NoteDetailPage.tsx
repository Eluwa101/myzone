import { CheckCheck, Pencil, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { listCustomers } from "../api/customers";
import { deleteNote, getNote, updateNote } from "../api/notes";
import { errorMessage } from "../api/errorMessage";
import type { Customer, OrgNote } from "../api/types";
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
  const [confirmDelete, setConfirmDelete] = useState(false);
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
            {note.is_pending_review && <span className="badge badge-lead">Needs review</span>}
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

          <div className="card-actions" style={{ marginTop: 12 }}>
            {note.is_pending_review && (
              <button type="button" className="btn-primary" onClick={markReviewed} disabled={busy}>
                <CheckCheck size={14} /> Mark reviewed
              </button>
            )}
            <button type="button" onClick={() => setEditing(true)} disabled={busy}>
              <Pencil size={14} /> Edit
            </button>
            {confirmDelete ? (
              <button type="button" className="btn-danger" onClick={remove} disabled={busy}>
                <Trash2 size={14} /> Really delete?
              </button>
            ) : (
              <button type="button" onClick={() => setConfirmDelete(true)} disabled={busy}>
                <Trash2 size={14} /> Delete
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
