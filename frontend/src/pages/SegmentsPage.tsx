import { Check, Copy, Mail, MessageCircle, Trash2, X } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { createSegment, deleteSegment, getSegmentMembers, listSegments, previewSegment, updateSegment } from "../api/segments";
import { errorMessage } from "../api/errorMessage";
import type { CustomerStatus, Segment, SegmentFilters, SegmentResult } from "../api/types";
import ErrorText from "../components/ErrorText";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";

const EMAIL_BATCH_SIZE = 40;

function describeFilters(f: SegmentFilters): string {
  const parts: string[] = [];
  if (f.status) parts.push(`Status: ${f.status}`);
  if (f.interest_contains) parts.push(`Interested in "${f.interest_contains}"`);
  if (f.has_consent === true) parts.push("Has consent");
  if (f.has_consent === false) parts.push("No consent recorded");
  if (f.search) parts.push(`Matches "${f.search}"`);
  if (f.last_purchase_within_days) parts.push(`Bought in last ${f.last_purchase_within_days}d`);
  if (f.last_purchase_over_days) parts.push(`No purchase in ${f.last_purchase_over_days}d`);
  if (f.min_transactions) parts.push(`≥${f.min_transactions} purchases`);
  return parts.length ? parts.join(" · ") : "Everyone";
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
      <TopBar title="Segments" backTo="/settings" />
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

function FilterForm({ filters, onChange }: { filters: SegmentFilters; onChange: (f: SegmentFilters) => void }) {
  function set<K extends keyof SegmentFilters>(key: K, value: SegmentFilters[K]) {
    onChange({ ...filters, [key]: value });
  }

  return (
    <>
      <label htmlFor="seg-status">Status</label>
      <select id="seg-status" value={filters.status ?? ""} onChange={(e) => set("status", (e.target.value || null) as CustomerStatus | null)}>
        <option value="">Any</option>
        <option value="lead">Lead</option>
        <option value="customer">Customer</option>
        <option value="inactive">Inactive</option>
      </select>

      <label htmlFor="seg-interest">Interested in contains</label>
      <input
        id="seg-interest"
        value={filters.interest_contains ?? ""}
        onChange={(e) => set("interest_contains", e.target.value || null)}
        placeholder="e.g. Generator"
      />

      <label htmlFor="seg-search">Name / phone / email contains</label>
      <input id="seg-search" value={filters.search ?? ""} onChange={(e) => set("search", e.target.value || null)} />

      <label htmlFor="seg-consent">Consent</label>
      <select
        id="seg-consent"
        value={filters.has_consent === true ? "yes" : filters.has_consent === false ? "no" : ""}
        onChange={(e) => set("has_consent", e.target.value === "" ? null : e.target.value === "yes")}
      >
        <option value="">Any</option>
        <option value="yes">Has consent</option>
        <option value="no">No consent recorded</option>
      </select>

      <div className="tx-edit-grid">
        <div>
          <label htmlFor="seg-within">Bought within (days)</label>
          <input
            id="seg-within"
            type="number"
            min={1}
            value={filters.last_purchase_within_days ?? ""}
            onChange={(e) => set("last_purchase_within_days", e.target.value ? Number(e.target.value) : null)}
          />
        </div>
        <div>
          <label htmlFor="seg-over">No purchase in (days)</label>
          <input
            id="seg-over"
            type="number"
            min={1}
            value={filters.last_purchase_over_days ?? ""}
            onChange={(e) => set("last_purchase_over_days", e.target.value ? Number(e.target.value) : null)}
          />
        </div>
      </div>

      <label htmlFor="seg-min-tx">Minimum number of purchases</label>
      <input
        id="seg-min-tx"
        type="number"
        min={1}
        value={filters.min_transactions ?? ""}
        onChange={(e) => set("min_transactions", e.target.value ? Number(e.target.value) : null)}
      />
    </>
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
  const [filters, setFilters] = useState<SegmentFilters>(initial?.filters ?? {});
  const [preview, setPreview] = useState<SegmentResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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

      <FilterForm filters={filters} onChange={setFilters} />

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
