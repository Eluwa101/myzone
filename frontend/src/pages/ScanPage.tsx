import { Camera, CheckCircle2, FileWarning, ImageUp, Loader2, ScanLine, XCircle } from "lucide-react";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../api/errorMessage";
import { listScans, startScan, type DocumentScan, type ScanStatus } from "../api/scans";
import ErrorText from "../components/ErrorText";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";
import { fileToCompressedDataUrl } from "../utils/image";

const STATUS: Record<ScanStatus, { label: string; className: string; Icon: typeof CheckCircle2 }> = {
  processing: { label: "Reading…", className: "scan-status-processing", Icon: Loader2 },
  done: { label: "Recorded", className: "scan-status-done", Icon: CheckCircle2 },
  needs_review: { label: "Nothing recorded", className: "scan-status-review", Icon: FileWarning },
  failed: { label: "Couldn't read", className: "scan-status-failed", Icon: XCircle },
};

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

/** Photograph receipts, order slips and notes with a customer ID (CR004)
 * on them. Each is read in the background and recorded on that customer
 * automatically; the bell says what was done. */
export default function ScanPage() {
  const [scans, setScans] = useState<DocumentScan[] | null>(null);
  const [hint, setHint] = useState("");
  const [uploading, setUploading] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const filesRef = useRef<HTMLInputElement>(null);

  function load() {
    listScans()
      .then(setScans)
      .catch((err) => setError(errorMessage(err)));
  }
  useEffect(load, []);

  // poll while anything is still being read
  const processing = (scans ?? []).some((s) => s.status === "processing") || uploading > 0;
  useEffect(() => {
    if (!processing) return;
    const handle = setInterval(load, 3000);
    return () => clearInterval(handle);
  }, [processing]);

  async function onFiles(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = "";
    if (files.length === 0) return;
    setError(null);
    setUploading((n) => n + files.length);
    for (const file of files) {
      try {
        // receipts need more detail than chat photos - keep small print legible
        const dataUrl = await fileToCompressedDataUrl(file, 2200, 0.85);
        await startScan(dataUrl, hint.trim() || undefined);
      } catch (err) {
        setError(`${file.name}: ${errorMessage(err)}`);
      } finally {
        setUploading((n) => n - 1);
        load();
      }
    }
  }

  return (
    <div>
      <TopBar title="Scan documents" />
      <p className="muted small page-note">
        Photograph a receipt, order slip, form or note with a customer ID on it (like CR004). It's read automatically and recorded on
        that customer: sales, orders, contact details and anything else on it. The bell tells you what was done.
      </p>

      <div className="card scan-actions">
        <input ref={cameraRef} type="file" accept="image/*" capture="environment" hidden onChange={onFiles} />
        <input ref={filesRef} type="file" accept="image/*" multiple hidden onChange={onFiles} />
        <div className="row">
          <button type="button" className="btn-primary" onClick={() => cameraRef.current?.click()}>
            <Camera size={16} /> Take photo
          </button>
          <button type="button" onClick={() => filesRef.current?.click()}>
            <ImageUp size={16} /> Upload photos
          </button>
        </div>
        <label htmlFor="scan-hint" className="small" style={{ marginTop: 10 }}>
          Anything the reader should know? (optional)
        </label>
        <input id="scan-hint" value={hint} onChange={(e) => setHint(e.target.value)} placeholder="e.g. these are last week's order slips" maxLength={500} />
        {uploading > 0 && (
          <p className="small muted" style={{ marginBottom: 0 }}>
            Uploading {uploading} photo{uploading === 1 ? "" : "s"}…
          </p>
        )}
        <ErrorText message={error} />
        <ul className="small muted scan-rules">
          <li>Nothing is recorded if the customer ID is missing or unknown, or if the name on the paper doesn't match that customer.</li>
          <li>Existing profile details are never overwritten - differences are saved in a note for you to check.</li>
          <li>The same photo, or a sale that's already recorded, is skipped. Photos aren't stored - only what was read from them.</li>
        </ul>
      </div>

      <h2 className="settings-section-heading">Recent scans</h2>
      {scans === null ? (
        <Spinner />
      ) : scans.length === 0 ? (
        <div className="empty-state">
          <ScanLine size={40} className="empty-state-icon" strokeWidth={1.5} />
          <p>No scans yet.</p>
        </div>
      ) : (
        <div className="card-grid">
          {scans.map((s) => {
          const { label, className, Icon } = STATUS[s.status] ?? STATUS.failed;
          return (
            <div key={s.id} className="card scan-card">
              <div className="row-between" style={{ borderBottom: "none", alignItems: "flex-start" }}>
                <span>
                  <b>{s.summary || (s.document_type ? `A ${s.document_type}` : "Document")}</b>
                  <span className="muted small">
                    {" "}
                    · {when(s.created_at)}
                    {s.display_id && (
                      <>
                        {" "}
                        · {s.customer_id ? <Link to={`/customers/${s.customer_id}`}>{s.display_id}</Link> : s.display_id}
                      </>
                    )}
                  </span>
                </span>
                <span className={`scan-status ${className}`}>
                  <Icon size={13} className={s.status === "processing" ? "spin" : undefined} /> {label}
                </span>
              </div>
              {s.actions.length > 0 && (
                <ul className="small scan-action-list">
                  {s.actions.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
              )}
              {s.status === "needs_review" && s.actions.length === 0 && (
                <p className="small muted" style={{ margin: "6px 0 0" }}>
                  {s.error || (s.display_id ? `Couldn't safely match this to ${s.display_id}.` : "No customer ID was found on it.")} Add
                  the details by hand, or retake the photo with the ID clearly visible.
                </p>
              )}
              {s.status === "failed" && <p className="small muted" style={{ margin: "6px 0 0" }}>{s.error || "Try a clearer, closer photo."}</p>}
            </div>
          );
          })}
        </div>
      )}
    </div>
  );
}
