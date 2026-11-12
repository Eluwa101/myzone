import { Bot, Check, Code2, Copy, ExternalLink, ListFilter, Mail, MessageCircle, Sparkles, Trash2, X } from "lucide-react";
import { lazy, Suspense, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  createSegment,
  deleteSegment,
  getSegmentFields,
  getSegmentMembers,
  listSegments,
  previewSegment,
  previewSqlSegment,
  suggestSegmentFilters,
  updateSegment,
} from "../api/segments";
import { errorMessage } from "../api/errorMessage";
import type { Segment, SegmentFieldsCatalog, SegmentFilters, SegmentMember, SegmentNode, SegmentResult } from "../api/types";
import ErrorText from "../components/ErrorText";
import SegmentQueryBuilder, { emptyGroup, OPERATOR_LABELS } from "../components/SegmentQueryBuilder";
import SqlSegmentEditor from "../components/SqlSegmentEditor";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";

// pulls in the rich-text editor, so only load it once someone opens "Reach segment"
const EmailComposer = lazy(() => import("../components/EmailComposer"));

const EMAIL_BATCH_SIZE = 40;

function personalize(message: string, member: SegmentMember): string {
  const firstName = member.first_name || member.name.split(" ")[0] || "";
  return message.replaceAll("{first_name}", firstName);
}

function waLink(phone: string, message: string): string {
  const digits = phone.replace(/\D/g, "");
  return `https://wa.me/${digits}?text=${encodeURIComponent(message)}`;
}

function describeNode(node: SegmentNode): string {
  if (node.type === "condition") {
    const fieldLabel = node.field.startsWith("extra.") ? node.field.slice(6) : node.field.replace(/_/g, " ");
    const opLabel = OPERATOR_LABELS[node.operator] ?? node.operator;
    if (node.operator === "is_set" || node.operator === "is_not_set") return `${fieldLabel} ${opLabel}`;
    if (node.operator === "between") return `${fieldLabel} ${opLabel} ${node.value} and ${node.value2}`;
    if (node.operator === "in_list" || node.operator === "not_in_list") return `${fieldLabel} ${opLabel} [${(node.values ?? []).join(", ")}]`;
    return `${fieldLabel} ${opLabel} "${node.value}"`;
  }
  if (node.conditions.length === 0) return "everyone";
  const joiner = node.combinator === "and" ? " and " : node.combinator === "or" ? " or " : " nor ";
  return node.conditions.map((c) => (c.type === "group" ? `(${describeNode(c)})` : describeNode(c))).join(joiner);
}

function describeFilters(f: SegmentFilters): string {
  return f.conditions.length === 0 ? "Everyone" : describeNode(f);
}

export default function SegmentsPage() {
  const [segments, setSegments] = useState<Segment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  function load() {
    listSegments()
      .then(setSegments)
      .catch((err) => setError(errorMessage(err)));
  }

  useEffect(load, []);

  return (
    <div>
      <TopBar title="Segments" backTo="/data" />
      <p className="muted small page-note">
        Define a group of customers by filters - always resolved live, never a stale snapshot - then email or WhatsApp
        everyone in it at once.
      </p>
      <ErrorText message={error} />

      <div className="card">
        {creating ? (
          <SegmentBuilder onCancel={() => setCreating(false)} onSaved={() => { setCreating(false); load(); }} />
        ) : (
          <button type="button" className="icon-btn btn-ghost" onClick={() => setCreating(true)}>
            + New segment
          </button>
        )}
      </div>

      {!segments ? (
        <Spinner />
      ) : segments.length === 0 ? (
        <p className="muted small page-note">No segments yet.</p>
      ) : (
        segments.map((s) => <SegmentCard key={s.id} segment={s} onChanged={load} />)
      )}
    </div>
  );
}

function SegmentBuilder({
  initial,
  onCancel,
  onSaved,
}: {
  initial?: Segment;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [filters, setFilters] = useState<SegmentFilters>(initial?.filters ?? emptyGroup());
  const [catalog, setCatalog] = useState<SegmentFieldsCatalog | null>(null);
  const [preview, setPreview] = useState<SegmentResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [description, setDescription] = useState("");
  const [suggesting, setSuggesting] = useState(false);
  const [suggestError, setSuggestError] = useState<string | null>(null);
  const [appliedSummary, setAppliedSummary] = useState<string | null>(null);
  const [mode, setMode] = useState<"builder" | "sql">(initial?.sql ? "sql" : "builder");
  const [sql, setSql] = useState(initial?.sql ?? "");
  const [sqlError, setSqlError] = useState<string | null>(null);

  useEffect(() => {
    getSegmentFields()
      .then(setCatalog)
      .catch((err) => setError(errorMessage(err)));
  }, []);

  async function onSuggest() {
    if (!description.trim()) return;
    setSuggesting(true);
    setSuggestError(null);
    setAppliedSummary(null);
    try {
      const suggested = await suggestSegmentFilters(description.trim());
      setFilters(suggested);
      setAppliedSummary(describeFilters(suggested));
    } catch (err) {
      setSuggestError(errorMessage(err));
    } finally {
      setSuggesting(false);
    }
  }

  useEffect(() => {
    if (mode !== "builder") return;
    const handle = setTimeout(() => {
      previewSegment(filters)
        .then(setPreview)
        .catch(() => setPreview(null));
    }, 300);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters), mode]);

  useEffect(() => {
    if (mode !== "sql") return;
    setPreview(null);
    setSqlError(null);
    if (!sql.trim()) return;
    let cancelled = false;
    const handle = setTimeout(() => {
      previewSqlSegment(sql)
        .then((r) => !cancelled && setPreview(r))
        .catch((err) => !cancelled && setSqlError(errorMessage(err)));
    }, 600);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [sql, mode]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    if (mode === "sql" && !sql.trim()) {
      setError("Write a query first, or switch back to Builder.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      // saving in Builder mode clears any SQL, so the filters take over again
      const payload = { name: name.trim(), filters, sql: mode === "sql" ? sql : "" };
      if (initial) await updateSegment(initial.id, payload);
      else await createSegment(payload);
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="info-row-editing" onSubmit={onSubmit}>
      <label htmlFor="seg-name">Segment name</label>
      <input id="seg-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Generator leads" autoFocus />

      <div className="editor-mode-tabs" role="tablist" aria-label="Segment type" style={{ marginTop: 10 }}>
        <button type="button" role="tab" aria-selected={mode === "builder"} className={mode === "builder" ? "active" : ""} onClick={() => setMode("builder")}>
          <ListFilter size={13} /> Builder
        </button>
        <button type="button" role="tab" aria-selected={mode === "sql"} className={mode === "sql" ? "active" : ""} onClick={() => setMode("sql")}>
          <Code2 size={13} /> SQL
        </button>
      </div>

      {mode === "sql" ? (
        <SqlSegmentEditor sql={sql} onChange={setSql} />
      ) : (
        <>
      <div className="card assistant-suggest-card">
        <label htmlFor="seg-describe">
          <Bot size={13} className="h3-icon" /> Describe who you want, and let the assistant set the filters
        </label>
        <div className="row">
          <input
            id="seg-describe"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g. leads interested in generators who haven't bought in 60 days"
            style={{ flex: 1 }}
          />
          <button type="button" onClick={onSuggest} disabled={suggesting || !description.trim()}>
            <Sparkles size={14} /> {suggesting ? "Thinking…" : "Suggest filters"}
          </button>
        </div>
        {appliedSummary && <p className="muted small">Applied: {appliedSummary} - adjust below if needed.</p>}
        <ErrorText message={suggestError} />
      </div>

      {catalog ? <SegmentQueryBuilder group={filters} catalog={catalog} onChange={setFilters} /> : <Spinner />}
        </>
      )}

      <div className="card" style={{ marginTop: 10 }}>
        {mode === "sql" && sqlError ? (
          <p className="small error-text" style={{ margin: 0 }}>
            {sqlError}
          </p>
        ) : (
          <p className="small" style={{ margin: 0 }}>
            {mode === "sql" && !sql.trim()
              ? "Matching customers will show here as you write."
              : preview
                ? `${preview.total} matching customer${preview.total === 1 ? "" : "s"}`
                : "Calculating…"}
          </p>
        )}
        {preview && preview.total > 0 && (
          <p className="muted small" style={{ margin: "4px 0 0" }}>
            {preview.members
              .slice(0, 5)
              .map((m) => m.name)
              .join(", ")}
            {preview.total > 5 ? `, +${preview.total - 5} more` : ""}
          </p>
        )}
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

function SegmentCard({ segment, onChanged }: { segment: Segment; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [members, setMembers] = useState<SegmentResult | null>(null);
  const [showMembers, setShowMembers] = useState(false);
  const [showReach, setShowReach] = useState(false);
  const [message, setMessage] = useState("");
  const [armedDelete, setArmedDelete] = useState(false);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSegmentMembers(segment.id)
      .then(setMembers)
      .catch((err) => setError(errorMessage(err)));
  }, [segment.id]);

  async function remove() {
    if (!armedDelete) {
      setArmedDelete(true);
      return;
    }
    try {
      await deleteSegment(segment.id);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  if (editing) {
    return (
      <div className="card note-card">
        <SegmentBuilder initial={segment} onCancel={() => setEditing(false)} onSaved={() => { setEditing(false); onChanged(); }} />
      </div>
    );
  }

  const emails = (members?.members ?? []).map((m) => m.email).filter((e): e is string => !!e);
  const phones = (members?.members ?? []).map((m) => m.phone).filter((p): p is string => !!p);

  const emailBatches: string[][] = [];
  for (let i = 0; i < emails.length; i += EMAIL_BATCH_SIZE) emailBatches.push(emails.slice(i, i + EMAIL_BATCH_SIZE));

  function mailtoHref(batch: string[]): string {
    return `mailto:?bcc=${encodeURIComponent(batch.join(","))}`;
  }

  async function copyNumbers() {
    try {
      await navigator.clipboard.writeText(phones.join("\n"));
      setCopyStatus("Phone numbers copied.");
    } catch {
      setCopyStatus("Could not copy - select the list manually.");
    }
  }

  return (
    <div className="card note-card">
      <div className="row-between" style={{ borderBottom: "none" }}>
        <b>{segment.name}</b>
        <span className="muted small">{members ? `${members.total} customer${members.total === 1 ? "" : "s"}` : "…"}</span>
      </div>
      {segment.sql ? (
        <details className="sql-reference">
          <summary className="muted small">
            <Code2 size={12} className="h3-icon" /> Custom SQL
          </summary>
          <pre className="sql-snippet">{segment.sql}</pre>
        </details>
      ) : (
        <p className="muted small">{describeFilters(segment.filters)}</p>
      )}

      <div className="row">
        <button type="button" onClick={() => setShowMembers((v) => !v)}>
          {showMembers ? "Hide" : "View"} members
        </button>
        <button type="button" onClick={() => setShowReach((v) => !v)}>
          Reach segment
        </button>
        <button type="button" onClick={() => setEditing(true)}>
          Edit
        </button>
      </div>

      {showMembers && members && (
        <div className="submissions-list">
          {members.members.length === 0 ? (
            <p className="muted small">No matches.</p>
          ) : (
            members.members.map((m) => (
              <Link key={m.id} to={`/customers/${m.id}`} className="row-between">
                <span>{m.name}</span>
                <span className="muted small">{m.email ?? m.phone ?? "—"}</span>
              </Link>
            ))
          )}
        </div>
      )}

      {showReach && members && (
        <div className="card" style={{ marginTop: 8 }}>
          <p className="small" style={{ margin: "0 0 6px" }}>
            <Mail size={13} className="h3-icon" /> <b>Email</b> - {emails.length} of {members.total} have an address. Each
            person gets their own copy, with merge tags filled in for them.
          </p>
          {members.total === 0 ? (
            <p className="muted small">No one is in this segment yet.</p>
          ) : (
            <Suspense fallback={<Spinner />}>
              <EmailComposer embedded segmentId={segment.id} recipients={members.members.map((m) => ({ id: m.id, name: m.name, email: m.email }))} />
            </Suspense>
          )}
          {emails.length > 0 && (
            <details className="small" style={{ marginTop: 10 }}>
              <summary className="muted">Or write it in your own email app (BCC, no merge tags)</summary>
              <div className="row" style={{ marginTop: 8 }}>
                {emailBatches.map((batch, i) => (
                  <a key={i} href={mailtoHref(batch)} className="btn-ghost">
                    Open email{emailBatches.length > 1 ? ` (batch ${i + 1}/${emailBatches.length}, ${batch.length})` : ` (${batch.length})`}
                  </a>
                ))}
              </div>
            </details>
          )}

          <hr className="section-divider" />

          <div>
            <p className="small" style={{ margin: "0 0 6px" }}>
              <MessageCircle size={13} className="h3-icon" /> <b>WhatsApp</b> - {phones.length} with a number
            </p>
            {phones.length === 0 ? (
              <p className="muted small">No one in this segment has a phone number on file.</p>
            ) : (
              <>
                <label htmlFor={`seg-message-${segment.id}`}>Message</label>
                <textarea id={`seg-message-${segment.id}`} rows={3} value={message} onChange={(e) => setMessage(e.target.value)} />
                <p className="muted small" style={{ marginTop: -6 }}>
                  Use <code>{"{first_name}"}</code> to personalize each chat link below.
                </p>
                <p className="muted small">
                  WhatsApp doesn't support one link for many recipients at once - copy these numbers and the message above
                  into a broadcast list in your WhatsApp app.
                </p>
                <button type="button" onClick={copyNumbers}>
                  <Copy size={14} /> Copy {phones.length} phone number{phones.length === 1 ? "" : "s"}
                </button>
                {copyStatus && <p className="muted small">{copyStatus}</p>}

                <p className="muted small" style={{ marginTop: 10 }}>
                  Or open a personalized chat one at a time:
                </p>
                <div className="submissions-list">
                  {(members?.members ?? [])
                    .filter((m) => m.phone)
                    .map((m) => (
                      <a
                        key={m.id}
                        href={waLink(m.phone!, personalize(message, m))}
                        target="_blank"
                        rel="noreferrer"
                        className="row-between"
                      >
                        <span>{m.name}</span>
                        <span className="muted small">
                          <ExternalLink size={12} className="h3-icon" /> {m.phone}
                        </span>
                      </a>
                    ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      <ErrorText message={error} />
      <div className="row" style={{ marginTop: 10 }}>
        <button type="button" className="btn-danger" onClick={remove} style={{ marginLeft: "auto" }}>
          <Trash2 size={15} /> {armedDelete ? "Confirm?" : "Delete"}
        </button>
      </div>
    </div>
  );
}
