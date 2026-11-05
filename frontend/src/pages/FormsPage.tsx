import { Check, Copy, ExternalLink, Plus, QrCode, Trash2, X } from "lucide-react";
import QRCodeLib from "qrcode";
import { useEffect, useState, type FormEvent } from "react";
import { createForm, deleteForm, listForms, listSubmissions, updateForm } from "../api/forms";
import { errorMessage } from "../api/errorMessage";
import type { CustomForm, FormFieldDef, FormSubmission } from "../api/types";
import ErrorText from "../components/ErrorText";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";

const STANDARD_FIELD_OPTIONS: { key: string; label: string }[] = [
  { key: "name", label: "Full name" },
  { key: "phone", label: "Phone / WhatsApp" },
  { key: "email", label: "Email" },
  { key: "job", label: "Job / occupation" },
  { key: "nationality", label: "Nationality" },
  { key: "pet", label: "Pet(s)" },
  { key: "address", label: "Address / city" },
  { key: "notes", label: "Notes" },
  { key: "interests", label: "Interested in" },
];

const DEFAULT_FIELDS: FormFieldDef[] = [{ key: "name", label: "Full name", type: "text", required: true, standard: true }];

function publicFormUrl(token: string): string {
  return `${window.location.origin}/f/${token}`;
}

export default function FormsPage() {
  const [forms, setForms] = useState<CustomForm[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  function load() {
    listForms()
      .then(setForms)
      .catch((err) => setError(errorMessage(err)));
  }

  useEffect(load, []);

  return (
    <div>
      <TopBar title="Forms" backTo="/settings" />
      <p className="muted small page-note">
        Build a custom intake form, share its link with customers, or use the link's API directly from Zapier, a Google
        Form's Apps Script, or any other tool that can POST JSON.
      </p>
      <ErrorText message={error} />

      <div className="card">
        {creating ? (
          <FormBuilder onCancel={() => setCreating(false)} onSaved={() => { setCreating(false); load(); }} />
        ) : (
          <button type="button" className="icon-btn btn-ghost" onClick={() => setCreating(true)}>
            <Plus size={15} /> New form
          </button>
        )}
      </div>

      {!forms ? <Spinner /> : forms.length === 0 ? <p className="muted small page-note">No forms yet.</p> : forms.map((f) => <FormCard key={f.id} form={f} onChanged={load} />)}
    </div>
  );
}

function FormCard({ form, onChanged }: { form: CustomForm; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [showQr, setShowQr] = useState(false);
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [showSubmissions, setShowSubmissions] = useState(false);
  const [armedDelete, setArmedDelete] = useState(false);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const link = publicFormUrl(form.public_token);

  async function toggleQr() {
    if (!showQr) {
      const dataUrl = await QRCodeLib.toDataURL(link, { width: 200 });
      setQrDataUrl(dataUrl);
    }
    setShowQr((v) => !v);
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(link);
      setCopyStatus("Link copied.");
    } catch {
      setCopyStatus("Could not copy. Select the link text.");
    }
  }

  async function toggleActive() {
    try {
      await updateForm(form.id, { is_active: !form.is_active });
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function regenerateToken() {
    try {
      await updateForm(form.id, { regenerate_token: true });
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function remove() {
    if (!armedDelete) {
      setArmedDelete(true);
      return;
    }
    try {
      await deleteForm(form.id);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  if (editing) {
    return (
      <div className="card note-card">
        <FormBuilder initialForm={form} onCancel={() => setEditing(false)} onSaved={() => { setEditing(false); onChanged(); }} />
      </div>
    );
  }

  return (
    <div className="card note-card">
      <div className="row-between" style={{ borderBottom: "none" }}>
        <b>{form.name}</b>
        {!form.is_active && <span className="badge badge-inactive">Inactive</span>}
      </div>
      <p className="muted small" style={{ wordBreak: "break-all" }}>
        {link}
      </p>
      <div className="row">
        <button type="button" onClick={copyLink}>
          <Copy size={14} /> Copy link
        </button>
        <a href={link} target="_blank" rel="noreferrer">
          <ExternalLink size={14} /> Open
        </a>
        <button type="button" onClick={toggleQr}>
          <QrCode size={14} /> QR code
        </button>
        <button type="button" onClick={() => setShowSubmissions((v) => !v)}>
          Submissions
        </button>
      </div>
      {copyStatus && <p className="muted small">{copyStatus}</p>}
      {showQr && qrDataUrl && (
        <div className="qr-preview">
          <img src={qrDataUrl} alt="Form QR code" width={160} height={160} />
        </div>
      )}
      {showSubmissions && <SubmissionsList formId={form.id} />}

      <ErrorText message={error} />
      <div className="row" style={{ marginTop: 10 }}>
        <button type="button" onClick={() => setEditing(true)}>
          Edit fields
        </button>
        <button type="button" onClick={toggleActive}>
          {form.is_active ? "Deactivate" : "Activate"}
        </button>
        <button type="button" onClick={regenerateToken} title="Invalidates the current link">
          New link
        </button>
        <button type="button" className="btn-danger" onClick={remove} style={{ marginLeft: "auto" }}>
          <Trash2 size={15} /> {armedDelete ? "Confirm?" : "Delete"}
        </button>
      </div>
    </div>
  );
}

function SubmissionsList({ formId }: { formId: string }) {
  const [items, setItems] = useState<FormSubmission[] | null>(null);

  useEffect(() => {
    listSubmissions(formId).then(setItems);
  }, [formId]);

  if (!items) return <p className="muted small">Loading…</p>;
  if (items.length === 0) return <p className="muted small">No submissions yet.</p>;

  return (
    <div style={{ marginTop: 8 }}>
      {items.map((s) => (
        <div key={s.id} className="info-row" style={{ cursor: "default" }}>
          <div className="info-row-text">
            <div className="info-row-value muted small">{new Date(s.created_at).toLocaleString()}</div>
            <div className="small">{Object.entries(s.raw_payload).map(([k, v]) => `${k}: ${v}`).join(" · ")}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function slugify(label: string): string {
  return (
    label
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "") || `field_${Date.now()}`
  );
}

function FormBuilder({
  initialForm,
  onCancel,
  onSaved,
}: {
  initialForm?: CustomForm;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(initialForm?.name ?? "");
  const [fields, setFields] = useState<FormFieldDef[]>(initialForm?.fields ?? DEFAULT_FIELDS);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const usedStandardKeys = new Set(fields.filter((f) => f.standard).map((f) => f.key));

  function update(i: number, patch: Partial<FormFieldDef>) {
    setFields((f) => f.map((field, idx) => (idx === i ? { ...field, ...patch } : field)));
  }

  function remove(i: number) {
    setFields((f) => f.filter((_, idx) => idx !== i));
  }

  function addStandard() {
    const next = STANDARD_FIELD_OPTIONS.find((o) => !usedStandardKeys.has(o.key));
    if (!next) return;
    setFields((f) => [...f, { key: next.key, label: next.label, type: "text", required: false, standard: true }]);
  }

  function addCustom() {
    setFields((f) => [...f, { key: slugify(""), label: "", type: "text", required: false, standard: false }]);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const cleaned = fields.map((f) => (f.standard ? f : { ...f, key: slugify(f.label) }));
      if (initialForm) await updateForm(initialForm.id, { name: name.trim(), fields: cleaned });
      else await createForm({ name: name.trim(), fields: cleaned });
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="info-row-editing" onSubmit={onSubmit}>
      <label htmlFor="form-name">Form name</label>
      <input id="form-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Lead intake form" autoFocus />

      <label>Fields</label>
      {fields.map((f, i) => (
        <div key={i} className="card" style={{ margin: "8px 0", padding: 12 }}>
          {f.standard ? (
            <>
              <label htmlFor={`field-key-${i}`}>Standard field</label>
              <select
                id={`field-key-${i}`}
                value={f.key}
                onChange={(e) => {
                  const opt = STANDARD_FIELD_OPTIONS.find((o) => o.key === e.target.value);
                  update(i, { key: e.target.value, label: opt?.label ?? e.target.value });
                }}
                disabled={f.key === "name"}
              >
                {STANDARD_FIELD_OPTIONS.filter((o) => o.key === f.key || !usedStandardKeys.has(o.key)).map((o) => (
                  <option key={o.key} value={o.key}>
                    {o.label}
                  </option>
                ))}
              </select>
            </>
          ) : (
            <>
              <label htmlFor={`field-label-${i}`}>Custom field label</label>
              <input id={`field-label-${i}`} value={f.label} onChange={(e) => update(i, { label: e.target.value })} placeholder="e.g. Preferred delivery day" />
            </>
          )}
          <div className="row" style={{ marginTop: 8 }}>
            <label className="row" style={{ gap: 6 }}>
              <input
                type="checkbox"
                checked={f.required}
                onChange={(e) => update(i, { required: e.target.checked })}
                disabled={f.key === "name"}
              />
              Required
            </label>
            {f.key !== "name" && (
              <button type="button" className="btn-danger" onClick={() => remove(i)} style={{ marginLeft: "auto" }}>
                <Trash2 size={14} />
              </button>
            )}
          </div>
        </div>
      ))}

      <div className="row" style={{ marginTop: 4 }}>
        <button type="button" onClick={addStandard} disabled={usedStandardKeys.size >= STANDARD_FIELD_OPTIONS.length}>
          <Plus size={14} /> Standard field
        </button>
        <button type="button" onClick={addCustom}>
          <Plus size={14} /> Custom field
        </button>
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
