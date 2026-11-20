import { Check, Copy, History, KeyRound, Pencil, Plug, Power, PowerOff, RefreshCw, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import {
  createSubscription,
  deleteSubscription,
  listEventTypes,
  listDeliveriesPaged,
  listSubscriptionsPaged,
  updateSubscription,
  type WebhookSubscriptionInput,
} from "../api/webhooks";
import { errorMessage } from "../api/errorMessage";
import type { WebhookDelivery, WebhookSubscription } from "../api/types";
import CardHead from "../components/CardHead";
import ErrorText from "../components/ErrorText";
import InfoTip from "../components/InfoTip";
import Pagination from "../components/Pagination";
import SearchBox from "../components/SearchBox";
import Spinner from "../components/Spinner";
import { usePagedList } from "../hooks/usePagedList";
import { useLocalPagedList } from "../hooks/useLocalPagedList";

const PAGE_SIZE = 20;
const SUB_PAGE_SIZE = 10;
import TopBar from "../components/TopBar";

function groupLabel(eventType: string): string {
  const [resource] = eventType.split(".");
  return resource.charAt(0).toUpperCase() + resource.slice(1) + "s";
}

export default function WebhooksPage() {
  const [eventTypes, setEventTypes] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const list = usePagedList<WebhookSubscription>({
    fetcher: ({ search, page, pageSize }) => listSubscriptionsPaged({ search, page, pageSize }),
    pageSize: PAGE_SIZE,
  });
  const { items: subs, error } = list;
  const load = list.reload;

  useEffect(() => {
    listEventTypes().then(setEventTypes);
  }, []);

  return (
    <div>
      <TopBar title="Webhooks" backTo="/data" />
      <p className="muted small page-note">
        Send a signed event to your own URL when something changes.{" "}
        <InfoTip>
          Get notified the moment something changes in your Shop - new customers, orders, transactions, or notes - by
          having this app POST a signed JSON event to a URL you control.
        </InfoTip>
      </p>
      <ErrorText message={error} />

      {creating ? (
        <div className="card form-card">
          <SubscriptionForm
            eventTypes={eventTypes}
            onCancel={() => setCreating(false)}
            onSaved={() => {
              setCreating(false);
              load();
            }}
          />
        </div>
      ) : (
        <div className="page-actions">
          <button type="button" className="btn-primary" onClick={() => setCreating(true)}>
            + New webhook
          </button>
          <SearchBox value={list.search} onChange={list.setSearch} label="Search webhooks" placeholder="Search by URL…" />
        </div>
      )}

      {list.loading ? (
        <Spinner />
      ) : subs.length === 0 ? (
        <p className="muted small page-note">{list.searching ? "No webhooks match that search." : "No webhooks yet."}</p>
      ) : (
        <div className="card-grid">
          {subs.map((s) => (
            <SubscriptionCard key={s.id} sub={s} eventTypes={eventTypes} onChanged={load} />
          ))}
        </div>
      )}
      {!list.loading && <Pagination page={list.page} pageSize={PAGE_SIZE} total={list.total} onChange={list.goToPage} />}
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
  const [showSecret, setShowSecret] = useState(false);
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
    try {
      await deleteSubscription(sub.id);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  if (editing) {
    return (
      <div className="card note-card span-all form-card">
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
      <CardHead
        icon={<Plug />}
        tone="blue"
        title={sub.target_url}
        subtitle={`${sub.event_types.length} event${sub.event_types.length === 1 ? "" : "s"}`}
        badges={!sub.is_active ? <span className="badge badge-inactive">Inactive</span> : undefined}
        items={[
          { key: "edit", label: "Edit", icon: <Pencil />, onSelect: () => setEditing(true) },
          {
            key: "active",
            label: sub.is_active ? "Deactivate" : "Activate",
            icon: sub.is_active ? <PowerOff /> : <Power />,
            onSelect: toggleActive,
          },
          { key: "deliveries", label: showDeliveries ? "Hide deliveries" : "Deliveries", icon: <History />, onSelect: () => setShowDeliveries((v) => !v) },
          { key: "secret", label: showSecret ? "Hide signing secret" : "Signing secret", icon: <KeyRound />, onSelect: () => setShowSecret((v) => !v) },
          { key: "div", divider: true },
          { key: "delete", label: "Delete webhook", icon: <Trash2 />, danger: true, confirm: "Really delete?", onSelect: remove },
        ]}
      />
      <div className="row" style={{ flexWrap: "wrap", gap: 4 }}>
        {sub.event_types.map((et) => (
          <span key={et} className="chip">
            {et}
          </span>
        ))}
      </div>

      {showSecret && (
        <div className="secret-panel">
          <div className="muted small">
            Signing secret{" "}
            <InfoTip>Every delivery includes an X-MyShop-Signature header: HMAC-SHA256 of the JSON body using this secret.</InfoTip>
          </div>
          <div className="row" style={{ alignItems: "center", flexWrap: "nowrap" }}>
            <code className="small" style={{ wordBreak: "break-all", flex: 1 }}>
              {sub.secret}
            </code>
            <button type="button" onClick={copySecret} aria-label="Copy secret">
              <Copy size={13} />
            </button>
            <button type="button" onClick={regenerateSecret} title="New secret (invalidates the current one)" aria-label="New secret (invalidates the current one)">
              <RefreshCw size={13} />
            </button>
          </div>
          {copyStatus && <p className="muted small" style={{ margin: "4px 0 0" }}>{copyStatus}</p>}
        </div>
      )}

      {showDeliveries && <DeliveriesList subscriptionId={sub.id} />}
      <ErrorText message={error} />
    </div>
  );
}

function DeliveriesList({ subscriptionId }: { subscriptionId: string }) {
  const { items, total, page, setPage } = useLocalPagedList<WebhookDelivery>(
    (p, size) => listDeliveriesPaged(subscriptionId, { page: p, pageSize: size }),
    SUB_PAGE_SIZE,
    subscriptionId
  );

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
      <Pagination page={page} pageSize={SUB_PAGE_SIZE} total={total} onChange={setPage} />
    </div>
  );
}
