import { ClipboardList, Download, Mail, Plug, ScanLine, StickyNote, Upload, UsersRound } from "lucide-react";
import { useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { exportCsv, importCsv } from "../api/customers";
import { errorMessage } from "../api/errorMessage";
import type { ImportResult } from "../api/types";
import type { CardTone } from "../components/CardHead";
import ErrorText from "../components/ErrorText";
import TopBar from "../components/TopBar";

const TILES: { to: string; title: string; text: string; icon: ReactNode; tone: CardTone }[] = [
  { to: "/segments", title: "Segments", text: "Group customers by filters, then email or WhatsApp everyone in the group at once.", icon: <UsersRound />, tone: "violet" },
  { to: "/messages", title: "Messages", text: "Email customers directly, with merge tags and reusable templates.", icon: <Mail />, tone: "teal" },
  { to: "/scan", title: "Scan documents", text: "Photograph receipts and notes with a customer ID - recorded automatically.", icon: <ScanLine />, tone: "blue" },
  { to: "/forms", title: "Forms", text: "A custom intake form you can share, or use as a webhook target for Zapier or Google Forms.", icon: <ClipboardList />, tone: "rose" },
  { to: "/webhooks", title: "Webhooks", text: "Get notified in real time when customers, orders, transactions or notes change.", icon: <Plug />, tone: "blue" },
  { to: "/notes", title: "Notes", text: "Creditors, VIPs, anything to flag - attachable to one or many customers.", icon: <StickyNote />, tone: "amber" },
];

function SectionHead({ title, text }: { title: string; text: string }) {
  return (
    <div className="section-head">
      <h2>{title}</h2>
      <p className="muted small">{text}</p>
    </div>
  );
}

export default function DataPage() {
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
      <SectionHead title="Automation & integrations" text="Reach your customers, collect their details, and connect other tools." />
      <div className="card-grid">
        {TILES.map((t) => (
          <Link key={t.to} to={t.to} className="card hub-tile">
            <span className={`card-icon tone-${t.tone}`} aria-hidden="true">
              {t.icon}
            </span>
            <span className="hub-tile-text">
              <b>{t.title}</b>
              <span className="muted small">{t.text}</span>
            </span>
          </Link>
        ))}
      </div>

      <SectionHead title="Import & export" text="Move your customer list in and out of MyShop as a CSV file." />
      <div className="card-grid">
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
    </div>
  );
}
