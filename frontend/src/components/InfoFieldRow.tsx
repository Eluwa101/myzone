import { Check, ChevronRight, Trash2 } from "lucide-react";
import { useState } from "react";
import CardMenu from "./CardMenu";
import InfoTip from "./InfoTip";

export interface SelectOption {
  value: string;
  label: string;
}

interface InfoFieldRowProps {
  label: string;
  value: string | null | undefined;
  type?: "text" | "tel" | "date" | "textarea" | "select";
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
  const [busy, setBusy] = useState(false);

  function startEdit() {
    setDraft(value ?? "");
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
      <div className="row" style={{ gap: 4, marginBottom: 2 }}>
        <label className="info-row-label" style={{ marginBottom: 0 }}>{label}</label>
        {type === "tel" && <InfoTip label="About phone numbers">Include the country code to use WhatsApp links, e.g. +234 801 234 5678.</InfoTip>}
      </div>
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
          <div style={{ marginLeft: "auto" }}>
            <CardMenu
              label={`More actions for ${label}`}
              items={[{ key: "delete", label: "Delete", icon: <Trash2 />, danger: true, confirm: "Really delete?", disabled: busy, onSelect: remove }]}
            />
          </div>
        )}
      </div>
    </div>
  );
}
