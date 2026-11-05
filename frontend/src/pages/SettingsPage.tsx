import { Copy, Download, QrCode, Upload } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useRef, useState } from "react";
import { exportCsv, importCsv } from "../api/customers";
import { errorMessage } from "../api/errorMessage";
import { getSettings, updateSettings } from "../api/settings";
import type { ImportResult } from "../api/types";
import ErrorText from "../components/ErrorText";
import TopBar from "../components/TopBar";

const DEFAULT_MESSAGE = "Hi! My name is [name] and I'm interested in [product/service]. I agree to my details being saved so you can reply to me.";

function waLink(number: string, message: string): string {
  const digits = number.replace(/\D/g, "");
  return `https://wa.me/${digits}?text=${encodeURIComponent(message || DEFAULT_MESSAGE)}`;
}

export default function SettingsPage() {
  const [bizName, setBizName] = useState("");
  const [number, setNumber] = useState("");
  const [message, setMessage] = useState(DEFAULT_MESSAGE);
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [qrStatus, setQrStatus] = useState<string | null>(null);
  const [savingQr, setSavingQr] = useState(false);

  const [importText, setImportText] = useState("");
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getSettings().then((s) => {
      setBizName(s.biz_name ?? "");
      setNumber(s.whatsapp_number ?? "");
      setMessage(s.qr_message ?? DEFAULT_MESSAGE);
      if (s.whatsapp_number) {
        QRCode.toDataURL(waLink(s.whatsapp_number, s.qr_message ?? DEFAULT_MESSAGE), { width: 220 }).then(setQrDataUrl);
      }
    });
  }, []);

  async function onSaveQr() {
    const digits = number.replace(/\D/g, "");
    if (!digits) {
      setQrStatus("Enter your WhatsApp number first.");
      return;
    }
    setSavingQr(true);
    setQrStatus(null);
    try {
      await updateSettings({ biz_name: bizName, whatsapp_number: number, qr_message: message || DEFAULT_MESSAGE });
      const dataUrl = await QRCode.toDataURL(waLink(number, message), { width: 220 });
      setQrDataUrl(dataUrl);
      setQrStatus("Saved.");
    } catch (err) {
      setQrStatus(errorMessage(err));
    } finally {
      setSavingQr(false);
    }
  }

  async function onCopyLink() {
    try {
      await navigator.clipboard.writeText(waLink(number, message));
      setQrStatus("Link copied.");
    } catch {
      setQrStatus("Could not copy. Select the link text.");
    }
  }

  async function onExport() {
    setExportError(null);
    try {
      const csv = await exportCsv();
      const blob = new Blob([csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "customers.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(errorMessage(err));
    }
  }

  async function onFileChosen(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportText(await file.text());
  }

  async function onImport() {
    if (!importText.trim()) return;
    setImporting(true);
    setImportError(null);
    setImportResult(null);
    try {
      const result = await importCsv(importText);
      setImportResult(result);
      if (result.added || result.merged) setImportText("");
    } catch (err) {
      setImportError(errorMessage(err));
    } finally {
      setImporting(false);
    }
  }

  return (
    <div>
      <TopBar title="Settings" />

      <div className="card">
        <h3>
          <QrCode size={15} className="h3-icon" /> WhatsApp QR for your counter
        </h3>
        <label htmlFor="set-biz">Business name (shown on the sign)</label>
        <input id="set-biz" value={bizName} onChange={(e) => setBizName(e.target.value)} placeholder="e.g. Ada's Store" />
        <label htmlFor="set-number">WhatsApp number (country code first, digits only)</label>
        <input id="set-number" value={number} onChange={(e) => setNumber(e.target.value)} placeholder="2348012345678" inputMode="tel" />
        <label htmlFor="set-message">Message customers will send (they can edit it)</label>
        <textarea id="set-message" rows={3} value={message} onChange={(e) => setMessage(e.target.value)} />
        <div className="row" style={{ marginTop: 12 }}>
          <button className="btn-primary" onClick={onSaveQr} disabled={savingQr}>
            {savingQr ? "Saving…" : "Save & show QR"}
          </button>
          {qrStatus && <span className="muted small">{qrStatus}</span>}
        </div>

        {qrDataUrl && (
          <div className="qr-preview">
            {bizName && <div className="qr-title">{bizName}</div>}
            <p className="muted small">Scan to chat with us on WhatsApp</p>
            <img src={qrDataUrl} alt="WhatsApp QR code" width={180} height={180} />
            <p className="muted small qr-link">{waLink(number, message)}</p>
            <button onClick={onCopyLink}>
              <Copy size={14} /> Copy link
            </button>
          </div>
        )}
      </div>

      <div className="card">
        <h3>
          <Download size={15} className="h3-icon" /> Export customers
        </h3>
        <p className="muted small">Download every customer and their transactions as a CSV file.</p>
        <button className="btn-primary" onClick={onExport}>
          <Download size={15} /> Export CSV
        </button>
        <ErrorText message={exportError} />
      </div>

      <div className="card">
        <h3>
          <Upload size={15} className="h3-icon" /> Import customers
        </h3>
        <p className="muted small">
          Only a name column is required. Common headings (Phone, Occupation, Country, Product, Price…) are recognized, and
          other columns become custom fields. Duplicates are merged automatically.
        </p>
        <input ref={fileInputRef} type="file" accept=".csv,text/csv" onChange={onFileChosen} />
        <label htmlFor="import-paste">…or paste CSV text (first line = column names)</label>
        <textarea id="import-paste" rows={6} value={importText} onChange={(e) => setImportText(e.target.value)} />
        <div className="row" style={{ marginTop: 10 }}>
          <button className="btn-primary" onClick={onImport} disabled={importing || !importText.trim()}>
            {importing ? "Importing…" : "Import"}
          </button>
        </div>
        <ErrorText message={importError} />
        {importResult && (
          <p className="small" style={{ marginTop: 10 }}>
            Done: {importResult.added} new, {importResult.merged} updated
            {importResult.skipped ? `, ${importResult.skipped} skipped (no name)` : ""}
            {importResult.failed ? `, ${importResult.failed} failed` : ""}.
            {importResult.errors.length > 0 && (
              <span className="error-text" style={{ display: "block" }}>
                {importResult.errors.join("; ")}
              </span>
            )}
          </p>
        )}
      </div>
    </div>
  );
}
