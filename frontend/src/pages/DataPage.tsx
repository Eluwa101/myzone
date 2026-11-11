import { ClipboardList, Download, Mail, Plug, StickyNote, Upload, Users } from "lucide-react";
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { exportCsv, importCsv } from "../api/customers";
import { errorMessage } from "../api/errorMessage";
import type { ImportResult } from "../api/types";
import ErrorText from "../components/ErrorText";
import TopBar from "../components/TopBar";

export default function DataPage() {
  const navigate = useNavigate();
  const [importText, setImportText] = useState("");
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
      <TopBar title="Data" />
      <p className="muted small page-note">Query, share, and move customer data in and out of MyShop.</p>

      <h2 className="settings-section-heading">Automation &amp; integrations</h2>
      <div className="card settings-automation-card">
        <div className="settings-automation-row">
          <div>
            <h3>
              <Users size={15} className="h3-icon" /> Segments
            </h3>
            <p className="muted small">Group customers by filters, then email or WhatsApp everyone in the group at once.</p>
          </div>
          <button type="button" className="btn-primary" onClick={() => navigate("/segments")}>
            Open
          </button>
        </div>
        <div className="settings-automation-row">
          <div>
            <h3>
              <Mail size={15} className="h3-icon" /> Messages
            </h3>
            <p className="muted small">Email customers directly from the app, with merge tags and reusable templates.</p>
          </div>
          <button type="button" className="btn-primary" onClick={() => navigate("/messages")}>
            Open
          </button>
        </div>
        <div className="settings-automation-row">
          <div>
            <h3>
              <ClipboardList size={15} className="h3-icon" /> Forms
            </h3>
            <p className="muted small">A custom intake form you can share, or use as a webhook target for Zapier, Google Forms, etc.</p>
          </div>
          <button type="button" className="btn-primary" onClick={() => navigate("/forms")}>
            Open
          </button>
        </div>
        <div className="settings-automation-row">
          <div>
            <h3>
              <Plug size={15} className="h3-icon" /> Webhooks
            </h3>
            <p className="muted small">Get notified in real time when customers, orders, transactions, or notes change.</p>
          </div>
          <button type="button" className="btn-primary" onClick={() => navigate("/webhooks")}>
            Open
          </button>
        </div>
        <div className="settings-automation-row">
          <div>
            <h3>
              <StickyNote size={15} className="h3-icon" /> Notes
            </h3>
            <p className="muted small">Org-wide notes - creditors, VIPs, anything to flag - attachable to one or many customers.</p>
          </div>
          <button type="button" className="btn-primary" onClick={() => navigate("/notes")}>
            Open
          </button>
        </div>
      </div>

      <h2 className="settings-section-heading">Import &amp; export</h2>
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
