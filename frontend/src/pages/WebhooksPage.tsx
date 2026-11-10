import { Check, Copy, Plug, RefreshCw, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import {
  createSubscription,
  deleteSubscription,
  listDeliveries,
  listEventTypes,
  listSubscriptions,
  updateSubscription,
  type WebhookSubscriptionInput,
} from "../api/webhooks";
import { errorMessage } from "../api/errorMessage";
import type { WebhookDelivery, WebhookSubscription } from "../api/types";
import ErrorText from "../components/ErrorText";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";

function groupLabel(eventType: string): string {
  const [resource] = eventType.split(".");
  return resource.charAt(0).toUpperCase() + resource.slice(1) + "s";
}

export default function WebhooksPage() {
  const [subs, setSubs] = useState<WebhookSubscription[] | null>(null);
  const [eventTypes, setEventTypes] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    listSubscriptions()
      .then(setSubs)
      .catch((err) => setError(errorMessage(err)));
  }

  useEffect(() => {
    load();
    listEventTypes().then(setEventTypes);
  }, []);

  return (
    <div>
      <TopBar title="Webhooks" backTo="/data" />
      <p className="muted small page-note">
        Get notified the moment something changes in your Shop - new customers, orders, transactions, or notes - by having
        this app POST a signed JSON event to a URL you control.
      </p>
      <ErrorText message={error} />

      <div className="card">
        {!creating ? (
          <button type="button" className="icon-btn btn-ghost" onClick={() => setCreating(true)}>
            + New webhook
          </button>
        ) : (
          <SubscriptionForm
            eventTypes={eventTypes}
            onCancel={() => setCreating(false)}
            onSaved={() => {
              setCreating(false);
              load();
            }}
          />
        )}
      </div>

      {!subs ? (
        <Spinner />
      ) : subs.length === 0 ? (
        <p className="muted small page-note">No webhooks yet.</p>
      ) : (
        subs.map((s) => <SubscriptionCard key={s.id} sub={s} eventTypes={eventTypes} onChanged={load} />)
      )}
    </div>
  );
}

function SubscriptionForm({
  initial,
  eventTypes,
  onCancel,
  onSaved,
}: {
  initial?: WebhookSubscription;
  eventTypes: string[];
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [targetUrl, setTargetUrl] = useState(initial?.target_url ?? "");
  const [selected, setSelected] = useState<Set<string>>(new Set(initial?.event_types ?? []));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const grouped = eventTypes.reduce<Record<string, string[]>>((acc, et) => {
    const g = groupLabel(et);
    (acc[g] ??= []).push(et);
    return acc;
  }, {});

  function toggle(et: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(et)) next.delete(et);
      else next.add(et);
      return next;
    });
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!targetUrl.trim() || selected.size === 0) return;
    setBusy(true);
    setError(null);
    const data: WebhookSubscriptionInput = { target_url: targetUrl.trim(), event_types: [...selected] };
    try {
      if (initial) await updateSubscription(initial.id, data);
      else await createSubscription(data);
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="info-row-editing" onSubmit={onSubmit}>
      <label htmlFor="wh-url">Target URL</label>
      <input
        id="wh-url"
        value={targetUrl}
        onChange={(e) => setTargetUrl(e.target.value)}
        placeholder="https://your-server.example.com/hooks/myshop"
        autoFocus
      />

      <label>Events to send</label>
      {Object.entries(grouped).map(([group, items]) => (
        <div key={group} style={{ margin: "6px 0" }}>
          <span className="muted small">{group}</span>
          <div className="row" style={{ flexWrap: "wrap" }}>
            {items.map((et) => (
              <label key={et} className="chip" style={{ cursor: "pointer" }}>
                <input type="checkbox" checked={selected.has(et)} onChange={() => toggle(et)} style={{ marginRight: 4 }} />
                {et}
              </label>
            ))}
          </div>
        </div>
      ))}

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

function SubscriptionCard({ sub, eventTypes, onChanged }: { sub: WebhookSubscription; eventTypes: string[]; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [showDeliveries, setShowDeliveries] = useState(false);
  const [armedDelete, setArmedDelete] = useState(false);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function copySecret() {
    try {
      await navigator.clipboard.writeText(sub.secret);
      setCopyStatus("Secret copied.");
    } catch {
      setCopyStatus("Could not copy. Select the text.");
    }
  }

  async function toggleActive() {
    try {
      await updateSubscription(sub.id, { is_active: !sub.is_active });
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function regenerateSecret() {
    try {
      await updateSubscription(sub.id, { regenerate_secret: true });
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
      await deleteSubscription(sub.id);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  if (editing) {
    return (
      <div className="card note-card">
        <SubscriptionForm
          initial={sub}
          eventTypes={eventTypes}
          onCancel={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            onChanged();
          }}
        />
      </div>
    );
  }

  return (
    <div className="card note-card">
      <div className="row-between" style={{ borderBottom: "none" }}>
        <b style={{ wordBreak: "break-all" }}>{sub.target_url}</b>
        {!sub.is_active && <span className="badge badge-inactive">Inactive</span>}
      </div>
      <div className="row" style={{ flexWrap: "wrap" }}>
        {sub.event_types.map((et) => (
          <span key={et} className="chip">
            {et}
          </span>
        ))}
      </div>

      <label className="muted small" style={{ marginTop: 8, display: "block" }}>
        Signing secret
      </label>
      <div className="row" style={{ alignItems: "center" }}>
        <code className="small" style={{ wordBreak: "break-all" }}>
          {sub.secret}
        </code>
        <button type="button" onClick={copySecret}>
          <Copy size={13} />
        </button>
        <button type="button" onClick={regenerateSecret} title="Invalidates the current secret">
          <RefreshCw size={13} /> New secret
        </button>
      </div>
      <p className="muted small">Every delivery includes an X-MyShop-Signature header: HMAC-SHA256 of the JSON body using this secret.</p>
      {copyStatus && <p className="muted small">{copyStatus}</p>}

      <div className="row" style={{ marginTop: 4 }}>
        <button type="button" onClick={() => setShowDeliveries((v) => !v)}>
          Deliveries
        </button>
      </div>
      {showDeliveries && <DeliveriesList subscriptionId={sub.id} />}

      <ErrorText message={error} />
      <div className="row" style={{ marginTop: 10 }}>
        <button type="button" onClick={() => setEditing(true)}>
          Edit
        </button>
        <button type="button" onClick={toggleActive}>
          {sub.is_active ? "Deactivate" : "Activate"}
        </button>
        <button type="button" className="btn-danger" onClick={remove} style={{ marginLeft: "auto" }}>
          <Trash2 size={15} /> {armedDelete ? "Confirm?" : "Delete"}
        </button>
      </div>
    </div>
  );
}

function DeliveriesList({ subscriptionId }: { subscriptionId: string }) {
  const [items, setItems] = useState<WebhookDelivery[] | null>(null);

  useEffect(() => {
    listDeliveries(subscriptionId).then(setItems);
  }, [subscriptionId]);

  if (!items) return <p className="muted small">Loading…</p>;
  if (items.length === 0) return <p className="muted small">No deliveries yet - they'll appear here once a matching event fires.</p>;

  return (
    <div className="submissions-list">
      {items.map((d) => (
        <div key={d.id} className="submission-card">
          <div className="row-between" style={{ borderBottom: "none", padding: "2px 0" }}>
            <span className="muted small">{new Date(d.created_at).toLocaleString()}</span>
            <span className={`chip ${d.status === "success" ? "" : "btn-danger"}`}>
              <Plug size={11} className="h3-icon" /> {d.event_type} - {d.status}
              {d.response_code ? ` (${d.response_code})` : ""}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
