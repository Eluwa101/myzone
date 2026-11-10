import { Bot, Check, Mic, Plus, Send, Square, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  addOrder,
  addTransaction,
  createCustomer,
  deleteCustomer,
  getCustomer,
  type CustomerInput,
  updateCustomer,
} from "../api/customers";
import { getThreadMessages, listPending, sendChat } from "../api/agent";
import { ApiError } from "../api/client";
import { errorMessage } from "../api/errorMessage";
import { listNotes } from "../api/notes";
import type { Customer, CustomerStatus, Order, OrgNote, PendingAction } from "../api/types";
import CurrencySelect from "../components/CurrencySelect";
import ErrorText from "../components/ErrorText";
import InfoFieldRow from "../components/InfoFieldRow";
import MarkdownMessage from "../components/MarkdownMessage";
import OrderItemsEditor, { hasPricedItems, itemsTotal } from "../components/OrderItemsEditor";
import OrderRow from "../components/OrderRow";
import PendingActionCard from "../components/PendingActionCard";
import PendingSyncBadge from "../components/PendingSyncBadge";
import Spinner from "../components/Spinner";
import Tabs from "../components/Tabs";
import TopBar from "../components/TopBar";
import TransactionLinesEditor, { blankLine, type TransactionLine } from "../components/TransactionLinesEditor";
import TransactionRow from "../components/TransactionRow";
import { useVoiceAutoSend } from "../hooks/useVoiceAutoSend";
import { withOfflineFallback } from "../offline/queue";
import { usePendingSync } from "../offline/usePendingSync";

const BLANK: CustomerInput = { first_name: "", last_name: "", phone: "", email: "" };
const STATUS_OPTIONS = [
  { value: "lead", label: "Lead" },
  { value: "customer", label: "Customer" },
  { value: "inactive", label: "Inactive" },
];

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const isNew = id === "new";
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [form, setForm] = useState<CustomerInput>(BLANK);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<{ message: string; existingId: string } | null>(null);
  const [armedDelete, setArmedDelete] = useState(false);
  const initialTab = searchParams.get("tab");
  const [tab, setTab] = useState<"info" | "transactions" | "orders" | "assistant">(
    initialTab === "transactions" || initialTab === "orders" || initialTab === "assistant" ? initialTab : "info"
  );
  const autoOpenAdd = searchParams.get("new") === "1";

  function loadCustomer() {
    if (!id || isNew) return;
    setLoading(true);
    getCustomer(id)
      .then((c) => {
        setCustomer(c);
        setForm({ name: c.name });
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }

  useEffect(loadCustomer, [id, isNew]);

  function set<K extends keyof CustomerInput>(key: K, value: CustomerInput[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function onCreate(e: FormEvent, force = false) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setConflict(null);
    try {
      const created = await createCustomer(form, force);
      navigate(`/customers/${created.id}`, { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const detail = err.detail as { message: string; existing_id: string };
        setConflict({ message: detail.message, existingId: detail.existing_id });
      } else {
        setError(errorMessage(err));
      }
    } finally {
      setSaving(false);
    }
  }

  async function saveField(key: keyof CustomerInput, value: string, isDate = false) {
    if (!id) return;
    const payload = { [key]: isDate && !value ? null : value } as Partial<CustomerInput>;
    const result = await withOfflineFallback(() => updateCustomer(id, payload), {
      method: "PATCH",
      path: `/api/customers/${id}`,
      body: payload,
      label: `Update ${String(key)}`,
    });
    if (result.queued) {
      setCustomer((c) => (c ? ({ ...c, ...payload } as Customer) : c));
    } else {
      loadCustomer();
    }
  }

  async function saveExtraField(key: string, value: string) {
    if (!id || !customer) return;
    const extra = { ...customer.extra, [key]: value };
    const result = await withOfflineFallback(() => updateCustomer(id, { extra }), {
      method: "PATCH",
      path: `/api/customers/${id}`,
      body: { extra },
      label: `Update custom field: ${key}`,
    });
    if (result.queued) setCustomer((c) => (c ? { ...c, extra } : c));
    else loadCustomer();
  }

  async function deleteExtraField(key: string) {
    if (!id || !customer) return;
    const next = { ...customer.extra };
    delete next[key];
    const result = await withOfflineFallback(() => updateCustomer(id, { extra: next }), {
      method: "PATCH",
      path: `/api/customers/${id}`,
      body: { extra: next },
      label: `Remove custom field: ${key}`,
    });
    if (result.queued) setCustomer((c) => (c ? { ...c, extra: next } : c));
    else loadCustomer();
  }

  async function onDeleteCustomer() {
    if (!id) return;
    if (!armedDelete) {
      setArmedDelete(true);
      return;
    }
    setSaving(true);
    try {
      await deleteCustomer(id);
      navigate("/customers");
    } catch (err) {
      setError(errorMessage(err));
      setSaving(false);
    }
  }

  if (loading) return <Spinner />;

  if (isNew) {
    return (
      <div>
        <TopBar title="New customer" backTo="/customers" />
        <form className="card" onSubmit={onCreate}>
          <label htmlFor="cf-first-name">First name *</label>
          <input id="cf-first-name" value={form.first_name ?? ""} onChange={(e) => set("first_name", e.target.value)} required autoFocus />
          <label htmlFor="cf-last-name">Last name</label>
          <input id="cf-last-name" value={form.last_name ?? ""} onChange={(e) => set("last_name", e.target.value)} />
          <label htmlFor="cf-phone">Phone / WhatsApp</label>
          <input id="cf-phone" value={form.phone ?? ""} onChange={(e) => set("phone", e.target.value)} />
          <label htmlFor="cf-email">Email</label>
          <input id="cf-email" type="email" value={form.email ?? ""} onChange={(e) => set("email", e.target.value)} />
          <label htmlFor="cf-interests">Interested in</label>
          <input
            id="cf-interests"
            value={form.interests ?? ""}
            onChange={(e) => set("interests", e.target.value)}
            placeholder="Generator, Rice (comma-separated)"
          />
          <p className="muted small">You can add more info, transactions, and custom fields once this is saved.</p>

          <ErrorText message={error} />
          {conflict && (
            <div className="card conflict-card">
              <p>{conflict.message}</p>
              <div className="row">
                <button type="button" onClick={() => navigate(`/customers/${conflict.existingId}`)}>
                  View existing
                </button>
                <button type="button" className="btn-primary" onClick={(e) => onCreate(e, true)}>
                  Save as new anyway
                </button>
              </div>
            </div>
          )}

          <button className="btn-primary" type="submit" disabled={saving} style={{ marginTop: 12 }}>
            {saving ? "Saving…" : "Save"}
          </button>
        </form>
      </div>
    );
  }

  if (!customer) return null;

  return (
    <div>
      <TopBar title={customer.name} backTo="/customers" />
      <Tabs
        tabs={[
          { key: "info", label: "Info" },
          { key: "transactions", label: `Transactions (${customer.transactions.length})` },
          { key: "orders", label: `Orders (${customer.orders.length})` },
          { key: "assistant", label: "Assistant" },
        ]}
        active={tab}
        onChange={(k) => setTab(k as "info" | "transactions" | "orders" | "assistant")}
      />

      <ErrorText message={error} />

      {tab === "info" ? (
        <InfoTab
          customer={customer}
          onSaveField={saveField}
          onSaveExtra={saveExtraField}
          onDeleteExtra={deleteExtraField}
          onDeleteCustomer={onDeleteCustomer}
          armedDelete={armedDelete}
          deleting={saving}
        />
      ) : tab === "transactions" ? (
        <TransactionsTab customer={customer} onChanged={loadCustomer} autoOpenAdd={autoOpenAdd} />
      ) : tab === "orders" ? (
        <OrdersTab customer={customer} onChanged={loadCustomer} autoOpenAdd={autoOpenAdd} />
      ) : (
        <AssistantTab customer={customer} onChanged={loadCustomer} />
      )}
    </div>
  );
}

function InfoTab({
  customer,
  onSaveField,
  onSaveExtra,
  onDeleteExtra,
  onDeleteCustomer,
  armedDelete,
  deleting,
}: {
  customer: Customer;
  onSaveField: (key: keyof CustomerInput, value: string, isDate?: boolean) => Promise<void>;
  onSaveExtra: (key: string, value: string) => Promise<void>;
  onDeleteExtra: (key: string) => Promise<void>;
  onDeleteCustomer: () => void;
  armedDelete: boolean;
  deleting: boolean;
}) {
  const [addingField, setAddingField] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [addError, setAddError] = useState<string | null>(null);

  async function addField(e: FormEvent) {
    e.preventDefault();
    const key = newKey.trim();
    if (!key) return;
    setAddError(null);
    try {
      await onSaveExtra(key, newValue.trim());
      setNewKey("");
      setNewValue("");
      setAddingField(false);
    } catch (err) {
      setAddError(errorMessage(err));
    }
  }

  return (
    <div>
      <div className="card">
        <InfoFieldRow
          label="First name"
          value={customer.first_name || customer.name}
          deletable={false}
          onSave={(v) => onSaveField("first_name", v)}
        />
        <InfoFieldRow label="Last name" value={customer.last_name} onSave={(v) => onSaveField("last_name", v)} onDelete={() => onSaveField("last_name", "")} />
        <InfoFieldRow label="Phone / WhatsApp" value={customer.phone} onSave={(v) => onSaveField("phone", v)} onDelete={() => onSaveField("phone", "")} />
        <InfoFieldRow label="Email" value={customer.email} type="text" onSave={(v) => onSaveField("email", v)} onDelete={() => onSaveField("email", "")} />
        <InfoFieldRow label="Job / occupation" value={customer.job} onSave={(v) => onSaveField("job", v)} onDelete={() => onSaveField("job", "")} />
        <InfoFieldRow label="Nationality" value={customer.nationality} onSave={(v) => onSaveField("nationality", v)} onDelete={() => onSaveField("nationality", "")} />
        <InfoFieldRow label="Pet(s)" value={customer.pet} onSave={(v) => onSaveField("pet", v)} onDelete={() => onSaveField("pet", "")} />
        <InfoFieldRow
          label="Birthday"
          value={customer.birthday}
          type="date"
          onSave={(v) => onSaveField("birthday", v, true)}
          onDelete={() => onSaveField("birthday", "", true)}
        />
        <InfoFieldRow label="Address / city" value={customer.address} onSave={(v) => onSaveField("address", v)} onDelete={() => onSaveField("address", "")} />
        <InfoFieldRow
          label="Interested in"
          value={customer.interests}
          placeholder="Generator, Rice (comma-separated)"
          onSave={(v) => onSaveField("interests", v)}
          onDelete={() => onSaveField("interests", "")}
        />
        <InfoFieldRow
          label="Status"
          value={customer.status}
          type="select"
          options={STATUS_OPTIONS}
          allowBlank={false}
          deletable={false}
          onSave={(v) => onSaveField("status", v as CustomerStatus)}
        />
        <InfoFieldRow
          label="Consent to be stored (date given)"
          value={customer.consent_date}
          type="date"
          onSave={(v) => onSaveField("consent_date", v, true)}
          onDelete={() => onSaveField("consent_date", "", true)}
        />
        <InfoFieldRow label="Notes" value={customer.notes} type="textarea" onSave={(v) => onSaveField("notes", v)} onDelete={() => onSaveField("notes", "")} />
      </div>

      <div className="card">
        <h3>Other info</h3>
        {Object.entries(customer.extra).length === 0 && !addingField && <p className="muted small">No custom fields yet.</p>}
        {Object.entries(customer.extra).map(([key, value]) => (
          <InfoFieldRow key={key} label={key} value={value} onSave={(v) => onSaveExtra(key, v)} onDelete={() => onDeleteExtra(key)} />
        ))}

        {addingField ? (
          <form className="info-row-editing" onSubmit={addField}>
            <label htmlFor="new-field-key">Field name</label>
            <input id="new-field-key" value={newKey} onChange={(e) => setNewKey(e.target.value)} placeholder="e.g. Car" autoFocus />
            <label htmlFor="new-field-value">Value</label>
            <input id="new-field-value" value={newValue} onChange={(e) => setNewValue(e.target.value)} />
            <ErrorText message={addError} />
            <div className="row" style={{ marginTop: 10 }}>
              <button type="submit" className="btn-primary">
                <Check size={15} /> Add
              </button>
              <button type="button" onClick={() => setAddingField(false)}>
                <X size={15} /> Cancel
              </button>
            </div>
          </form>
        ) : (
          <button type="button" className="icon-btn btn-ghost" style={{ marginTop: 8 }} onClick={() => setAddingField(true)}>
            <Plus size={15} /> Add field
          </button>
        )}
      </div>

      <CustomerNotesSection customerId={customer.id} />

      <div className="card">
        <button type="button" className="btn-danger" onClick={onDeleteCustomer} disabled={deleting}>
          <Trash2 size={15} />
          {armedDelete ? "Click again to confirm" : "Delete customer"}
        </button>
      </div>
    </div>
  );
}

function TransactionsTab({
  customer,
  onChanged,
  autoOpenAdd,
}: {
  customer: Customer;
  onChanged: () => void;
  autoOpenAdd?: boolean;
}) {
  const [adding, setAdding] = useState(!!autoOpenAdd);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [currency, setCurrency] = useState("");
  const [lines, setLines] = useState<TransactionLine[]>([blankLine()]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const { pending, add: addPending } = usePendingSync(onChanged);

  async function onAdd(e: FormEvent) {
    e.preventDefault();
    const cleanLines = lines.filter((l) => l.item.trim());
    if (cleanLines.length === 0) return;
    setError(null);
    setSaving(true);
    try {
      let anyQueued = false;
      for (const line of cleanLines) {
        const body = {
          date,
          item: line.item.trim(),
          qty: Number(line.qty) || 1,
          amount: Number(line.amount) || 0,
          currency,
        };
        const result = await withOfflineFallback(() => addTransaction(customer.id, body), {
          method: "POST",
          path: `/api/customers/${customer.id}/transactions`,
          body,
          label: `Transaction: ${body.item}`,
        });
        if (result.queued) {
          anyQueued = true;
          addPending(result.id, body);
        }
      }
      setLines([blankLine()]);
      setAdding(false);
      // onChanged() re-fetches from the server - pointless while offline,
      // and its loading state would unmount this tab and lose the
      // just-added pending rows. usePendingSync calls it once they sync.
      if (!anyQueued) onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <PurchaseSummary transactions={customer.transactions} />
      <div className="card">
        {customer.transactions.length === 0 && pending.length === 0 && !adding && <p className="muted small">No transactions yet.</p>}
        {customer.transactions.map((t) => (
          <TransactionRow key={t.id} customerId={customer.id} transaction={t} onChanged={onChanged} />
        ))}
        {pending.map((p) => (
          <div key={p.id} className="row-between" style={{ opacity: 0.7 }}>
            <span>
              {p.data.item} <PendingSyncBadge />
            </span>
            <span className="muted small">
              {p.data.qty} × {p.data.currency} {p.data.amount}
            </span>
          </div>
        ))}

      {adding ? (
        <form className="info-row-editing" onSubmit={onAdd}>
          <div className="tx-edit-grid">
            <div>
              <label htmlFor="new-tx-date">Date</label>
              <input id="new-tx-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} autoFocus />
            </div>
            <div>
              <label htmlFor="new-tx-currency">Currency</label>
              <CurrencySelect id="new-tx-currency" value={currency} onChange={setCurrency} />
            </div>
          </div>
          <label>Items</label>
          <TransactionLinesEditor lines={lines} onChange={setLines} />
          <ErrorText message={error} />
          <div className="row" style={{ marginTop: 10 }}>
            <button type="submit" className="btn-primary" disabled={saving}>
              <Check size={15} /> {saving ? "Adding…" : "Add"}
            </button>
            <button type="button" onClick={() => setAdding(false)} disabled={saving}>
              <X size={15} /> Cancel
            </button>
          </div>
        </form>
      ) : (
        <button type="button" className="icon-btn btn-ghost" style={{ marginTop: 8 }} onClick={() => setAdding(true)}>
          <Plus size={15} /> Add transaction
        </button>
      )}
      </div>
    </div>
  );
}

function PurchaseSummary({ transactions }: { transactions: Customer["transactions"] }) {
  if (transactions.length === 0) return null;

  const byCurrency = new Map<string, number>();
  for (const t of transactions) {
    const key = t.currency || "";
    byCurrency.set(key, (byCurrency.get(key) ?? 0) + Number(t.amount || 0) * Number(t.qty || 1));
  }
  const dates = transactions.map((t) => t.date).sort();
  const first = dates[0];
  const last = dates[dates.length - 1];

  return (
    <div className="card">
      <h3>Purchase summary</h3>
      <div className="row-between">
        <span className="muted small">Total spent</span>
        <span>
          {Array.from(byCurrency.entries())
            .map(([cur, total]) => `${cur ? cur + " " : ""}${total.toLocaleString(undefined, { minimumFractionDigits: 2 })}`)
            .join(" + ")}
        </span>
      </div>
      <div className="row-between">
        <span className="muted small">Transactions</span>
        <span>{transactions.length}</span>
      </div>
      <div className="row-between">
        <span className="muted small">First · last purchase</span>
        <span>
          {first} · {last}
        </span>
      </div>
    </div>
  );
}

function OrdersTab({
  customer,
  onChanged,
  autoOpenAdd,
}: {
  customer: Customer;
  onChanged: () => void;
  autoOpenAdd?: boolean;
}) {
  const [adding, setAdding] = useState(!!autoOpenAdd);
  const [orderDate, setOrderDate] = useState(new Date().toISOString().slice(0, 10));
  const [deliveryDate, setDeliveryDate] = useState("");
  const [items, setItems] = useState<Order["items"]>([]);
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { pending, add: addPending } = usePendingSync(onChanged);

  function updateItems(next: Order["items"]) {
    setItems(next);
    if (hasPricedItems(next)) setAmount(String(itemsTotal(next)));
  }

  async function onAdd(e: FormEvent) {
    e.preventDefault();
    const cleanItems = items.filter((it) => it.name.trim());
    if (cleanItems.length === 0) return;
    setError(null);
    try {
      const body = {
        order_date: orderDate,
        delivery_date: deliveryDate || null,
        items: cleanItems,
        amount: amount.trim() ? Number(amount) : null,
        currency: currency || null,
      };
      const result = await withOfflineFallback(() => addOrder(customer.id, body), {
        method: "POST",
        path: `/api/customers/${customer.id}/orders`,
        body,
        label: `Order: ${cleanItems.map((i) => i.name).join(", ")}`,
      });
      if (result.queued) addPending(result.id, body);
      setItems([]);
      setDeliveryDate("");
      setAmount("");
      setAdding(false);
      if (!result.queued) onChanged();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="card">
      {customer.orders.length === 0 && pending.length === 0 && !adding && <p className="muted small">No orders yet.</p>}
      {customer.orders.map((o) => (
        <OrderRow key={o.id} customerId={customer.id} order={o} onChanged={onChanged} />
      ))}
      {pending.map((p) => (
        <div key={p.id} className="row-between" style={{ opacity: 0.7 }}>
          <span>
            {p.data.items.map((i) => i.name).join(", ")} <PendingSyncBadge />
          </span>
          <span className="muted small">{p.data.order_date}</span>
        </div>
      ))}

      {adding ? (
        <form className="info-row-editing" onSubmit={onAdd}>
          <div className="tx-edit-grid">
            <div>
              <label htmlFor="new-order-date">Order date</label>
              <input id="new-order-date" type="date" value={orderDate} onChange={(e) => setOrderDate(e.target.value)} autoFocus />
            </div>
            <div>
              <label htmlFor="new-order-delivery">Delivery date</label>
              <input id="new-order-delivery" type="date" value={deliveryDate} onChange={(e) => setDeliveryDate(e.target.value)} />
            </div>
          </div>
          <label>Items</label>
          <OrderItemsEditor items={items} onChange={updateItems} />
          <div className="tx-edit-grid">
            <div>
              <label htmlFor="new-order-amount">Amount</label>
              <input id="new-order-amount" type="number" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </div>
            <div>
              <label htmlFor="new-order-currency">Currency</label>
              <CurrencySelect id="new-order-currency" value={currency} onChange={setCurrency} />
            </div>
          </div>
          <ErrorText message={error} />
          <div className="row" style={{ marginTop: 10 }}>
            <button type="submit" className="btn-primary">
              <Check size={15} /> Add
            </button>
            <button type="button" onClick={() => setAdding(false)}>
              <X size={15} /> Cancel
            </button>
          </div>
        </form>
      ) : (
        <button type="button" className="icon-btn btn-ghost" style={{ marginTop: 8 }} onClick={() => setAdding(true)}>
          <Plus size={15} /> Add order
        </button>
      )}
    </div>
  );
}

interface AssistantMessage {
  role: "user" | "assistant";
  content: string;
}

function AssistantTab({ customer, onChanged }: { customer: Customer; onChanged: () => void }) {
  const threadId = `customer:${customer.id}`;
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [pending, setPending] = useState<PendingAction[]>([]);
  const [input, setInput] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  function refreshPending() {
    listPending()
      .then((all) =>
        setPending(
          all.filter((p) => {
            const payload = p.payload as Record<string, unknown>;
            return payload.customer_id === customer.id || payload.keep_id === customer.id || payload.merge_id === customer.id;
          })
        )
      )
      .catch(() => {
        /* non-fatal - chat still works without this */
      });
  }

  useEffect(() => {
    setLoaded(false);
    getThreadMessages(threadId)
      .then((history) => setMessages(history.map((m) => ({ role: m.role, content: m.content }))))
      .catch(() => setMessages([]))
      .finally(() => setLoaded(true));
    refreshPending();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

  async function doSend() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setError(null);
    setMessages((m) => [...m, { role: "user", content: text }]);
    setBusy(true);
    try {
      const res = await sendChat(text, threadId, undefined, customer.id);
      setMessages((m) => [...m, { role: "assistant", content: res.reply }]);
      if (res.pending_actions.length) refreshPending();
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const { voice, autoSendCountdown, cancelAutoSend, onMicClick } = useVoiceAutoSend(input, setInput, doSend);

  function onSend(e: FormEvent) {
    e.preventDefault();
    cancelAutoSend();
    doSend();
  }

  return (
    <div className="card assistant-tab">
      <p className="muted small">
        <Bot size={13} className="h3-icon" /> Ask it to log an order, add a transaction or note, or update info for{" "}
        <b>{customer.name}</b> - it already knows which customer you mean.
      </p>

      {pending.map((p) => (
        <PendingActionCard
          key={p.id}
          action={p}
          onResolved={() => {
            refreshPending();
            onChanged();
          }}
        />
      ))}

      <div className="chat-transcript assistant-tab-transcript">
        {!loaded ? (
          <Spinner />
        ) : messages.length === 0 ? (
          <p className="muted small">No conversation yet about {customer.name}.</p>
        ) : (
          messages.map((m, i) => (
            <div key={i} className={`chat-bubble ${m.role}`}>
              {m.role === "assistant" ? <MarkdownMessage content={m.content} /> : m.content}
            </div>
          ))
        )}
        {busy && <div className="chat-bubble assistant muted">Thinking…</div>}
        <div ref={bottomRef} />
      </div>

      <ErrorText message={error} />
      {autoSendCountdown !== null && (
        <div className="auto-send-banner row-between">
          <span>Sending in {autoSendCountdown}s…</span>
          <div className="row" style={{ gap: 8 }}>
            <button type="button" className="btn-ghost small" onClick={cancelAutoSend}>
              Cancel
            </button>
            <button
              type="button"
              className="btn-primary small"
              onClick={() => {
                cancelAutoSend();
                doSend();
              }}
            >
              Send now
            </button>
          </div>
        </div>
      )}
      <form className="chat-input-row" onSubmit={onSend}>
        {voice.supported && (
          <button
            type="button"
            className={`icon-btn${voice.listening ? " btn-danger" : ""}`}
            onClick={onMicClick}
            disabled={busy}
            aria-label={voice.listening ? "Stop dictation" : "Dictate message"}
            title={voice.listening ? "Stop dictation" : "Dictate message"}
          >
            {voice.listening ? <Square size={16} /> : <Mic size={16} />}
          </button>
        )}
        <input
          aria-label="Message"
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            cancelAutoSend();
          }}
          placeholder={voice.listening ? "Listening…" : `Ask about ${customer.name}…`}
          disabled={busy}
        />
        <button className="btn-primary" type="submit" disabled={busy || !input.trim()} aria-label="Send message">
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}

function CustomerNotesSection({ customerId }: { customerId: string }) {
  const [notes, setNotes] = useState<OrgNote[] | null>(null);

  useEffect(() => {
    listNotes({ customerId })
      .then(setNotes)
      .catch(() => setNotes([]));
  }, [customerId]);

  return (
    <div className="card">
      <h3>Notes</h3>
      {notes === null && <p className="muted small">Loading…</p>}
      {notes !== null && notes.length === 0 && <p className="muted small">No notes for this customer yet.</p>}
      {notes?.map((n) => (
        <div key={n.id} className="info-row" style={{ cursor: "default" }}>
          <div className="info-row-text">
            <div className="row" style={{ marginBottom: 2 }}>
              <span className="info-row-label" style={{ marginBottom: 0, fontWeight: 600, fontSize: 14, color: "var(--text)" }}>
                {n.title}
              </span>
              {n.is_pending_review && <span className="badge badge-lead">Needs review</span>}
            </div>
            <div className="info-row-value muted" style={{ fontWeight: 400 }}>
              {n.content}
            </div>
          </div>
        </div>
      ))}
      <Link to={`/notes?customer_id=${customerId}`} className="icon-btn btn-ghost" style={{ marginTop: 8, display: "inline-flex" }}>
        <Plus size={15} /> Add note
      </Link>
    </div>
  );
}
