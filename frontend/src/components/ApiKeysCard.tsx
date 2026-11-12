import { Copy, KeyRound, Plus } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { createApiKey, listApiKeys, revokeApiKey, type ApiKey, type CreatedApiKey } from "../api/apiKeys";
import { errorMessage } from "../api/errorMessage";
import ErrorText from "./ErrorText";

function when(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "never";
}

/** Settings card for creating and revoking API keys. A new key is shown
 * exactly once - the server keeps only a hash of it. */
export default function ApiKeysCard() {
  const [keys, setKeys] = useState<ApiKey[] | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [fresh, setFresh] = useState<CreatedApiKey | null>(null);
  const [copied, setCopied] = useState(false);
  const [armedRevoke, setArmedRevoke] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    listApiKeys()
      .then(setKeys)
      .catch((err) => setError(errorMessage(err)));
  }
  useEffect(load, []);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createApiKey(name.trim());
      setFresh(created);
      setCopied(false);
      setName("");
      load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function onRevoke(id: string) {
    if (armedRevoke !== id) {
      setArmedRevoke(id);
      return;
    }
    setArmedRevoke(null);
    try {
      await revokeApiKey(id);
      if (fresh?.id === id) setFresh(null);
      load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function copy() {
    if (!fresh) return;
    try {
      await navigator.clipboard.writeText(fresh.key);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  const active = (keys ?? []).filter((k) => !k.revoked_at);
  const revoked = (keys ?? []).filter((k) => k.revoked_at);

  return (
    <div className="card">
      <h3>
        <KeyRound size={15} className="h3-icon" /> API keys
      </h3>
      <p className="muted small">
        Let another app or a script read and update your data - see the <Link to="/developers">developer guide</Link>. A key can do
        anything you can in the app, so keep it secret and revoke it if it leaks.
      </p>

      <form className="row" onSubmit={onCreate}>
        <input aria-label="Key name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Name, e.g. Zapier or Website form" style={{ flex: 1 }} maxLength={100} />
        <button type="submit" disabled={busy || !name.trim()}>
          <Plus size={14} /> {busy ? "Creating…" : "Create key"}
        </button>
      </form>

      {fresh && (
        <div className="api-key-fresh">
          <p className="small" style={{ margin: "0 0 6px" }}>
            <b>Copy your new key now</b> - for your security it won't be shown again.
          </p>
          <div className="row" style={{ alignItems: "center", flexWrap: "nowrap" }}>
            <code className="api-key-value">{fresh.key}</code>
            <button type="button" onClick={copy}>
              <Copy size={14} /> {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <button type="button" className="btn-ghost small" style={{ marginTop: 6 }} onClick={() => setFresh(null)}>
            I've saved it
          </button>
        </div>
      )}

      <ErrorText message={error} />

      {keys && active.length === 0 && !fresh && <p className="muted small">No API keys yet.</p>}
      {active.map((k) => (
        <div key={k.id} className="row-between api-key-row">
          <span>
            <b>{k.name}</b>
            <span className="muted small">
              {" "}
              · <code>{k.prefix}…</code> · created {when(k.created_at)} · last used {when(k.last_used_at)}
            </span>
          </span>
          <button type="button" className="btn-danger small" onClick={() => onRevoke(k.id)}>
            {armedRevoke === k.id ? "Revoke - can't undo?" : "Revoke"}
          </button>
        </div>
      ))}
      {revoked.length > 0 && (
        <details className="small" style={{ marginTop: 8 }}>
          <summary className="muted">{revoked.length} revoked</summary>
          {revoked.map((k) => (
            <p key={k.id} className="muted small" style={{ margin: "4px 0" }}>
              {k.name} · <code>{k.prefix}…</code> · revoked {when(k.revoked_at)}
            </p>
          ))}
        </details>
      )}
    </div>
  );
}
