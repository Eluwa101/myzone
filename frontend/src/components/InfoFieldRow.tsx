import { Check, ChevronRight, Trash2 } from "lucide-react";
import { useState } from "react";

export interface SelectOption {
  value: string;
  label: string;
}

interface InfoFieldRowProps {
  label: string;
  value: string | null | undefined;
  type?: "text" | "date" | "textarea" | "select";
  options?: SelectOption[];
  allowBlank?: boolean;
  placeholder?: string;
  deletable?: boolean;
  onSave: (value: string) => Promise<void>;
  onDelete?: () => Promise<void>;
}

export default function InfoFieldRow({
  label,
  value,
  type = "text",
  options,
  allowBlank = true,
  placeholder,
  deletable = true,
  onSave,
  onDelete,
}: InfoFieldRowProps) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(value ?? "");
  const [armedDelete, setArmedDelete] = useState(false);
  const [busy, setBusy] = useState(false);

  function startEdit() {
    setDraft(value ?? "");
    setArmedDelete(false);
    setOpen(true);
  }

  async function save() {
    setBusy(true);
    try {
      await onSave(draft);
      setOpen(false);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!onDelete) return;
    if (!armedDelete) {
      setArmedDelete(true);
      return;
    }
    setBusy(true);
    try {
      await onDelete();
      setOpen(false);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button type="button" className="info-row" onClick={startEdit}>
        <div className="info-row-text">
          <div className="info-row-label">{label}</div>
          <div className={value ? "info-row-value" : "info-row-value muted"}>{value || "Not set"}</div>
        </div>
        <ChevronRight size={16} className="muted" />
      </button>
    );
  }

  return (
    <div className="info-row-editing">
      <label className="info-row-label">{label}</label>
      {type === "textarea" ? (
        <textarea rows={3} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={placeholder} autoFocus />
      ) : type === "select" ? (
        <select value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus>
          {allowBlank && <option value="">—</option>}
          {options?.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      ) : (
        <input type={type} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={placeholder} autoFocus />
      )}
      <div className="row" style={{ marginTop: 10 }}>
        <button type="button" className="btn-primary" onClick={save} disabled={busy}>
          <Check size={15} /> Save
        </button>
        <button type="button" onClick={() => setOpen(false)} disabled={busy}>
          Cancel
        </button>
        {deletable && onDelete && (
          <button type="button" className="btn-danger" onClick={remove} disabled={busy} style={{ marginLeft: "auto" }}>
            <Trash2 size={15} /> {armedDelete ? "Confirm?" : "Delete"}
          </button>
        )}
      </div>
    </div>
  );
}
