import { Check, ChevronDown, ChevronUp, Copy, ExternalLink, Package, QrCode, ShoppingBag, Trash2, User, Webhook, X } from "lucide-react";
import QRCodeLib from "qrcode";
import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { BASE_URL } from "../api/client";
import { createForm, deleteForm, listForms, listSubmissions, updateForm } from "../api/forms";
import { errorMessage } from "../api/errorMessage";
import type { CustomForm, FormFieldCategory, FormFieldDef, FormFieldType, FormSubmission } from "../api/types";
import ErrorText from "../components/ErrorText";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";

const CUSTOMER_FIELD_OPTIONS: { key: string; label: string; type: FormFieldType }[] = [
  { key: "first_name", label: "First name", type: "text" },
  { key: "last_name", label: "Last name", type: "text" },
  { key: "phone", label: "Phone / WhatsApp", type: "tel" },
  { key: "email", label: "Email", type: "email" },
  { key: "job", label: "Job / occupation", type: "text" },
  { key: "nationality", label: "Nationality", type: "text" },
  { key: "pet", label: "Pet(s)", type: "text" },
  { key: "address", label: "Address / city", type: "text" },
  { key: "notes", label: "Notes", type: "textarea" },
  { key: "interests", label: "Interested in", type: "text" },
];

const TRANSACTION_FIELD_OPTIONS: { key: string; label: string; type: FormFieldType }[] = [
  { key: "tx_item", label: "Item purchased", type: "text" },
  { key: "tx_qty", label: "Quantity", type: "number" },
  { key: "tx_amount", label: "Amount", type: "number" },
  { key: "tx_currency", label: "Currency", type: "text" },
  { key: "tx_date", label: "Purchase date", type: "date" },
];

const ORDER_FIELD_OPTIONS: { key: string; label: string; type: FormFieldType }[] = [
  { key: "order_item", label: "Item ordered", type: "text" },
  { key: "order_qty", label: "Quantity", type: "number" },
  { key: "order_price", label: "Price per item", type: "number" },
  { key: "order_currency", label: "Currency", type: "text" },
  { key: "order_date", label: "Order date", type: "date" },
  { key: "order_delivery_date", label: "Delivery date", type: "date" },
];

const CUSTOM_FIELD_TYPES: FormFieldType[] = ["text", "textarea", "tel", "email", "number", "date"];

// Every form - whatever it's for - collects these four so a record can be
// identified and reached; only first_name is locked required, matching the
// backend's REQUIRED_CONTACT_KEYS rule.
const CORE_CONTACT_FIELDS: FormFieldDef[] = [
  { key: "first_name", label: "First name", type: "text", required: true, category: "customer" },
  { key: "last_name", label: "Last name", type: "text", required: false, category: "customer" },
  { key: "phone", label: "Phone / WhatsApp", type: "tel", required: false, category: "customer" },
  { key: "email", label: "Email", type: "email", required: false, category: "customer" },
];
const LOCKED_KEYS = new Set(CORE_CONTACT_FIELDS.map((f) => f.key));

type FormTemplate = "order" | "transaction" | "customer" | "blank";

function templateFields(template: FormTemplate): FormFieldDef[] {
  if (template === "order") {
    return [
      ...CORE_CONTACT_FIELDS,
      { key: "order_item", label: "Item ordered", type: "text", required: true, category: "order" },
      { key: "order_qty", label: "Quantity", type: "number", required: false, category: "order" },
      { key: "order_price", label: "Price per item", type: "number", required: false, category: "order" },
    ];
  }
  if (template === "transaction") {
    return [
      ...CORE_CONTACT_FIELDS,
      { key: "tx_item", label: "Item purchased", type: "text", required: true, category: "transaction" },
      { key: "tx_amount", label: "Amount", type: "number", required: false, category: "transaction" },
    ];
  }
  return [...CORE_CONTACT_FIELDS];
}

function publicFormUrl(token: string): string {
  return `${window.location.origin}/f/${token}`;
}

function webhookSubmitUrl(token: string): string {
  return `${BASE_URL}/api/public/forms/${token}/submit`;
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

export default function FormsPage() {
  const [forms, setForms] = useState<CustomForm[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [template, setTemplate] = useState<FormTemplate | null>(null);

  function load() {
    listForms()
      .then(setForms)
      .catch((err) => setError(errorMessage(err)));
  }

  useEffect(load, []);

  function cancelCreate() {
    setCreating(false);
    setTemplate(null);
  }

  return (
    <div>
      <TopBar title="Forms" backTo="/data" />
      <p className="muted small page-note">
        Build a custom intake form, share its link with customers, or use the link's API directly from Zapier, a Google
        Form's Apps Script, or any other tool that can POST JSON. Every form always collects first name, last name, phone,
        and email.
      </p>
      <ErrorText message={error} />

      <div className="card">
        {!creating ? (
          <button type="button" className="icon-btn btn-ghost" onClick={() => setCreating(true)}>
            + New form
          </button>
        ) : template === null ? (
          <div>
            <label>What's this form for?</label>
            <div className="row" style={{ flexWrap: "wrap" }}>
              <button type="button" className="chip" onClick={() => setTemplate("order")}>
                <Package size={13} className="h3-icon" /> Order
              </button>
              <button type="button" className="chip" onClick={() => setTemplate("transaction")}>
                <ShoppingBag size={13} className="h3-icon" /> Transaction
              </button>
              <button type="button" className="chip" onClick={() => setTemplate("customer")}>
                <User size={13} className="h3-icon" /> Customer data
              </button>
            </div>
            <button type="button" onClick={cancelCreate} style={{ marginTop: 10 }}>
              <X size={14} /> Cancel
            </button>
          </div>
        ) : (
          <FormBuilder initialFields={templateFields(template)} onCancel={cancelCreate} onSaved={() => { cancelCreate(); load(); }} />
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
      {showSubmissions && <SubmissionsList formId={form.id} fields={form.fields} />}

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

      <WebhookPanel form={form} onChanged={onChanged} />
    </div>
  );
}

function WebhookPanel({ form, onChanged }: { form: CustomForm; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const submitUrl = webhookSubmitUrl(form.public_token);

  async function copy(text: string, label: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopyStatus(`${label} copied.`);
    } catch {
      setCopyStatus("Could not copy. Select the text.");
    }
  }

  async function toggleSigning() {
    setBusy(true);
    setError(null);
    try {
      if (form.webhook_secret) await updateForm(form.id, { disable_signing: true });
      else await updateForm(form.id, { enable_signing: true });
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function regenerateSecret() {
    setBusy(true);
    setError(null);
    try {
      await updateForm(form.id, { enable_signing: true });
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const curl = form.webhook_secret
    ? `BODY='{"first_name":"Ada","phone":"08012345678"}'\nSIG=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "${form.webhook_secret}" | sed 's/^.* //')\ncurl -X POST ${submitUrl} \\\n  -H "Content-Type: application/json" \\\n  -H "X-Signature: $SIG" \\\n  -d "$BODY"`
    : `curl -X POST ${submitUrl} \\\n  -H "Content-Type: application/json" \\\n  -d '{"first_name":"Ada","phone":"08012345678"}'`;

  return (
    <div style={{ marginTop: 10, borderTop: "1px solid var(--border)", paddingTop: 10 }}>
      <button type="button" className="btn-ghost" onClick={() => setOpen((v) => !v)}>
        <Webhook size={14} /> Webhook / API details {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      {open && (
        <div style={{ marginTop: 8 }}>
          <p className="muted small">
            POST JSON matching this form's field keys to the URL below from Zapier, Make, or any other tool - it behaves
            exactly like a submission, including creating or updating the matching customer record.
          </p>
          <label>Webhook URL (POST)</label>
          <div className="row" style={{ alignItems: "center" }}>
            <code className="small" style={{ wordBreak: "break-all" }}>
              {submitUrl}
            </code>
            <button type="button" onClick={() => copy(submitUrl, "URL")}>
              <Copy size={13} />
            </button>
          </div>

          <div className="row" style={{ marginTop: 10, alignItems: "center" }}>
            <label className="row" style={{ gap: 6 }}>
              <input type="checkbox" checked={!!form.webhook_secret} onChange={toggleSigning} disabled={busy} />
              Require signed requests (X-Signature header)
            </label>
          </div>
          {form.webhook_secret && (
            <>
              <label>Signing secret</label>
              <div className="row" style={{ alignItems: "center" }}>
                <code className="small" style={{ wordBreak: "break-all" }}>
                  {form.webhook_secret}
                </code>
                <button type="button" onClick={() => copy(form.webhook_secret!, "Secret")}>
                  <Copy size={13} />
                </button>
              </div>
              <button type="button" onClick={regenerateSecret} disabled={busy} style={{ marginTop: 6 }}>
                New secret
              </button>
            </>
          )}

          <label style={{ marginTop: 10 }}>Example</label>
          <pre className="small" style={{ whiteSpace: "pre-wrap", wordBreak: "break-all", background: "var(--surface-hover)", padding: 8, borderRadius: 6 }}>
            {curl}
          </pre>

          {copyStatus && <p className="muted small">{copyStatus}</p>}
          <ErrorText message={error} />
        </div>
      )}
    </div>
  );
}

function SubmissionsList({ formId, fields }: { formId: string; fields: FormFieldDef[] }) {
  const [items, setItems] = useState<FormSubmission[] | null>(null);
  const labelByKey = new Map(fields.map((f) => [f.key, f.label]));
  const categoryByKey = new Map(fields.map((f) => [f.key, f.category]));

  useEffect(() => {
    listSubmissions(formId).then(setItems);
  }, [formId]);

  if (!items) return <p className="muted small">Loading…</p>;
  if (items.length === 0) return <p className="muted small">No submissions yet.</p>;

  return (
    <div className="submissions-list">
      {items.map((s) => (
        <div key={s.id} className="submission-card">
          <div className="row-between" style={{ borderBottom: "none", padding: "2px 0" }}>
            <span className="muted small">{new Date(s.created_at).toLocaleString()}</span>
            {s.customer_id ? (
              <Link to={`/customers/${s.customer_id}`} className="chip">
                <User size={12} /> {s.customer_name ?? "View customer"}
              </Link>
            ) : (
              <span className="muted small">No record created</span>
            )}
          </div>
          <div className="submission-fields">
            {Object.entries(s.raw_payload).map(([k, v]) => (
              <div key={k} className="row-between" style={{ padding: "3px 0" }}>
                <span className="muted small">
                  {categoryByKey.get(k) === "transaction" && <ShoppingBag size={11} className="h3-icon" />}
                  {categoryByKey.get(k) === "order" && <Package size={11} className="h3-icon" />}
                  {labelByKey.get(k) ?? k}
                </span>
                <span className="small">{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function AddFieldPicker({ usedKeys, onAdd }: { usedKeys: Set<string>; onAdd: (f: FormFieldDef) => void }) {
  function onChange(e: ChangeEvent<HTMLSelectElement>) {
    const value = e.target.value;
    e.target.value = "";
    if (!value) return;
    if (value === "__custom__") {
      onAdd({ key: slugify(`field_${Date.now()}`), label: "", type: "text", required: false, category: "custom" });
      return;
    }
    const [category, key] = value.split(":") as [FormFieldCategory, string];
    const options = category === "customer" ? CUSTOMER_FIELD_OPTIONS : category === "transaction" ? TRANSACTION_FIELD_OPTIONS : ORDER_FIELD_OPTIONS;
    const opt = options.find((o) => o.key === key);
    if (opt) onAdd({ key: opt.key, label: opt.label, type: opt.type, required: false, category });
  }

  return (
    <select value="" onChange={onChange} aria-label="Add field">
      <option value="" disabled>
        + Add field…
      </option>
      <optgroup label="Customer fields">
        {CUSTOMER_FIELD_OPTIONS.filter((o) => !usedKeys.has(`customer:${o.key}`)).map((o) => (
          <option key={o.key} value={`customer:${o.key}`}>
            {o.label}
          </option>
        ))}
      </optgroup>
      <optgroup label="Transaction fields">
        {TRANSACTION_FIELD_OPTIONS.filter((o) => !usedKeys.has(`transaction:${o.key}`)).map((o) => (
          <option key={o.key} value={`transaction:${o.key}`}>
            {o.label}
          </option>
        ))}
      </optgroup>
      <optgroup label="Order fields">
        {ORDER_FIELD_OPTIONS.filter((o) => !usedKeys.has(`order:${o.key}`)).map((o) => (
          <option key={o.key} value={`order:${o.key}`}>
            {o.label}
          </option>
        ))}
      </optgroup>
      <option value="__custom__">+ Custom field…</option>
    </select>
  );
}

function isLocked(f: FormFieldDef): boolean {
  return f.category === "customer" && LOCKED_KEYS.has(f.key);
}

function FormBuilder({
  initialForm,
  initialFields,
  onCancel,
  onSaved,
}: {
  initialForm?: CustomForm;
  initialFields?: FormFieldDef[];
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(initialForm?.name ?? "");
  const [fields, setFields] = useState<FormFieldDef[]>(initialForm?.fields ?? initialFields ?? CORE_CONTACT_FIELDS);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const usedKeys = new Set(fields.filter((f) => f.category !== "custom").map((f) => `${f.category}:${f.key}`));

  function update(i: number, patch: Partial<FormFieldDef>) {
    setFields((f) => f.map((field, idx) => (idx === i ? { ...field, ...patch } : field)));
  }

  function remove(i: number) {
    setFields((f) => f.filter((_, idx) => idx !== i));
  }

  function addField(f: FormFieldDef) {
    setFields((prev) => [...prev, f]);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const cleaned = fields.map((f) => (f.category === "custom" ? { ...f, key: slugify(f.label || f.key) } : f));
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
          <div className="row-between" style={{ borderBottom: "none", padding: 0, marginBottom: 6 }}>
            <span className="muted small">
              {f.category === "customer" && (
                <>
                  <User size={11} className="h3-icon" /> Customer field
                </>
              )}
              {f.category === "transaction" && (
                <>
                  <ShoppingBag size={11} className="h3-icon" /> Transaction field
                </>
              )}
              {f.category === "order" && (
                <>
                  <Package size={11} className="h3-icon" /> Order field
                </>
              )}
              {f.category === "custom" && "Custom field"}
            </span>
          </div>
          <label htmlFor={`field-label-${i}`}>Label shown on the form</label>
          <input id={`field-label-${i}`} value={f.label} onChange={(e) => update(i, { label: e.target.value })} placeholder="e.g. Preferred delivery day" disabled={isLocked(f)} />
          {f.category === "custom" && (
            <>
              <label htmlFor={`field-type-${i}`}>Input type</label>
              <select id={`field-type-${i}`} value={f.type} onChange={(e) => update(i, { type: e.target.value as FormFieldType })}>
                {CUSTOM_FIELD_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </>
          )}
          <div className="row" style={{ marginTop: 8 }}>
            <label className="row" style={{ gap: 6 }}>
              <input type="checkbox" checked={f.required} onChange={(e) => update(i, { required: e.target.checked })} disabled={f.key === "first_name" && f.category === "customer"} />
              Required
            </label>
            {!isLocked(f) && (
              <button type="button" className="btn-danger" onClick={() => remove(i)} style={{ marginLeft: "auto" }}>
                <Trash2 size={14} />
              </button>
            )}
          </div>
        </div>
      ))}

      <div style={{ marginTop: 4 }}>
        <AddFieldPicker usedKeys={usedKeys} onAdd={addField} />
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
