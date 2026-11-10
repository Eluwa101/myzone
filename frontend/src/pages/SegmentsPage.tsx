import { Bot, Check, Copy, ExternalLink, Mail, MessageCircle, Sparkles, Trash2, X } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { createSegment, deleteSegment, getSegmentFields, getSegmentMembers, listSegments, previewSegment, suggestSegmentFilters, updateSegment } from "../api/segments";
import { errorMessage } from "../api/errorMessage";
import type { Segment, SegmentFieldsCatalog, SegmentFilters, SegmentMember, SegmentNode, SegmentResult } from "../api/types";
import ErrorText from "../components/ErrorText";
import SegmentQueryBuilder, { emptyGroup, OPERATOR_LABELS } from "../components/SegmentQueryBuilder";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";

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
    const handle = setTimeout(() => {
      previewSegment(filters)
        .then(setPreview)
        .catch(() => setPreview(null));
    }, 300);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters)]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      if (initial) await updateSegment(initial.id, { name: name.trim(), filters });
      else await createSegment({ name: name.trim(), filters });
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

      <div className="card" style={{ marginTop: 10 }}>
        <p className="small" style={{ margin: 0 }}>
          {preview ? `${preview.total} matching customer${preview.total === 1 ? "" : "s"}` : "Calculating…"}
        </p>
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
  const [subject, setSubject] = useState("");
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
    const params = new URLSearchParams();
    if (subject) params.set("subject", subject);
    if (message) params.set("body", message);
    params.set("bcc", batch.join(","));
    return `mailto:?${params.toString()}`;
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
      <p className="muted small">{describeFilters(segment.filters)}</p>

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
          <label htmlFor={`seg-subject-${segment.id}`}>Subject</label>
          <input id={`seg-subject-${segment.id}`} value={subject} onChange={(e) => setSubject(e.target.value)} />
          <label htmlFor={`seg-message-${segment.id}`}>Message</label>
          <textarea id={`seg-message-${segment.id}`} rows={3} value={message} onChange={(e) => setMessage(e.target.value)} />
          <p className="muted small" style={{ marginTop: -6 }}>
            Use <code>{"{first_name}"}</code> to personalize each message.
          </p>

          <div style={{ marginTop: 10 }}>
            <p className="small" style={{ margin: "0 0 6px" }}>
              <Mail size={13} className="h3-icon" /> Email ({emails.length} with an address - BCC'd, so no one sees the
              others)
            </p>
            {emails.length === 0 ? (
              <p className="muted small">No one in this segment has an email on file.</p>
            ) : (
              <div className="row">
                {emailBatches.map((batch, i) => (
                  <a key={i} href={mailtoHref(batch)} className="btn-primary">
                    Open email{emailBatches.length > 1 ? ` (batch ${i + 1}/${emailBatches.length}, ${batch.length})` : ` (${batch.length})`}
                  </a>
                ))}
              </div>
            )}
          </div>

          <div style={{ marginTop: 12 }}>
            <p className="small" style={{ margin: "0 0 6px" }}>
              <MessageCircle size={13} className="h3-icon" /> WhatsApp ({phones.length} with a number)
            </p>
            {phones.length === 0 ? (
              <p className="muted small">No one in this segment has a phone number on file.</p>
            ) : (
              <>
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
