import { Check, Plus, Trash2, X } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  addOrder,
  addTransaction,
  createCustomer,
  deleteCustomer,
  getCustomer,
  type CustomerInput,
  updateCustomer,
} from "../api/customers";
import { ApiError } from "../api/client";
import { errorMessage } from "../api/errorMessage";
import { listNotes } from "../api/notes";
import type { Customer, CustomerStatus, OrgNote } from "../api/types";
import ErrorText from "../components/ErrorText";
import InfoFieldRow from "../components/InfoFieldRow";
import OrderRow from "../components/OrderRow";
import Spinner from "../components/Spinner";
import Tabs from "../components/Tabs";
import TopBar from "../components/TopBar";
import TransactionRow from "../components/TransactionRow";

const BLANK: CustomerInput = { name: "" };
const STATUS_OPTIONS = [
  { value: "lead", label: "Lead" },
  { value: "customer", label: "Customer" },
  { value: "inactive", label: "Inactive" },
];

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const isNew = id === "new";
  const navigate = useNavigate();

  const [customer, setCustomer] = useState<Customer | null>(null);
  const [form, setForm] = useState<CustomerInput>(BLANK);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<{ message: string; existingId: string } | null>(null);
  const [armedDelete, setArmedDelete] = useState(false);
  const [tab, setTab] = useState<"info" | "transactions" | "orders">("info");

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
    await updateCustomer(id, payload);
    loadCustomer();
  }

  async function saveExtraField(key: string, value: string) {
    if (!id || !customer) return;
    await updateCustomer(id, { extra: { ...customer.extra, [key]: value } });
    loadCustomer();
  }

  async function deleteExtraField(key: string) {
    if (!id || !customer) return;
    const next = { ...customer.extra };
    delete next[key];
    await updateCustomer(id, { extra: next });
    loadCustomer();
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
        <TopBar title="New customer" />
        <form className="card" onSubmit={onCreate}>
          <label htmlFor="cf-name">Full name *</label>
          <input id="cf-name" value={form.name} onChange={(e) => set("name", e.target.value)} required autoFocus />
          <label htmlFor="cf-phone">Phone / WhatsApp</label>
          <input id="cf-phone" value={form.phone ?? ""} onChange={(e) => set("phone", e.target.value)} />
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
      <TopBar title={customer.name} />
      <Tabs
        tabs={[
          { key: "info", label: "Info" },
          { key: "transactions", label: `Transactions (${customer.transactions.length})` },
          { key: "orders", label: `Orders (${customer.orders.length})` },
        ]}
        active={tab}
        onChange={(k) => setTab(k as "info" | "transactions" | "orders")}
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
        <TransactionsTab customer={customer} onChanged={loadCustomer} />
      ) : (
        <OrdersTab customer={customer} onChanged={loadCustomer} />
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
        <InfoFieldRow label="Full name" value={customer.name} deletable={false} onSave={(v) => onSaveField("name", v)} />
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

function TransactionsTab({ customer, onChanged }: { customer: Customer; onChanged: () => void }) {
  const [adding, setAdding] = useState(false);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [item, setItem] = useState("");
  const [qty, setQty] = useState("1");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onAdd(e: FormEvent) {
    e.preventDefault();
    if (!item.trim()) return;
    setError(null);
    try {
      await addTransaction(customer.id, {
        date,
        item: item.trim(),
        qty: Number(qty) || 1,
        amount: Number(amount) || 0,
        currency: currency.toUpperCase(),
      });
      setItem("");
      setAmount("");
      setAdding(false);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="card">
      {customer.transactions.length === 0 && !adding && <p className="muted small">No transactions yet.</p>}
      {customer.transactions.map((t) => (
        <TransactionRow key={t.id} customerId={customer.id} transaction={t} onChanged={onChanged} />
      ))}

      {adding ? (
        <form className="info-row-editing" onSubmit={onAdd}>
          <div className="tx-edit-grid">
            <div>
              <label htmlFor="new-tx-date">Date</label>
              <input id="new-tx-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} autoFocus />
            </div>
            <div>
              <label htmlFor="new-tx-item">Item</label>
              <input id="new-tx-item" value={item} onChange={(e) => setItem(e.target.value)} />
            </div>
            <div>
              <label htmlFor="new-tx-qty">Qty</label>
              <input id="new-tx-qty" type="number" value={qty} onChange={(e) => setQty(e.target.value)} />
            </div>
            <div>
              <label htmlFor="new-tx-amount">Amount</label>
              <input id="new-tx-amount" type="number" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </div>
            <div>
              <label htmlFor="new-tx-currency">Currency</label>
              <input id="new-tx-currency" value={currency} onChange={(e) => setCurrency(e.target.value)} />
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
          <Plus size={15} /> Add transaction
        </button>
      )}
    </div>
  );
}

function OrdersTab({ customer, onChanged }: { customer: Customer; onChanged: () => void }) {
  const [adding, setAdding] = useState(false);
  const [orderDate, setOrderDate] = useState(new Date().toISOString().slice(0, 10));
  const [deliveryDate, setDeliveryDate] = useState("");
  const [itemsText, setItemsText] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onAdd(e: FormEvent) {
    e.preventDefault();
    if (!itemsText.trim()) return;
    setError(null);
    try {
      await addOrder(customer.id, {
        order_date: orderDate,
        delivery_date: deliveryDate || null,
        items: itemsText
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean)
          .map((name) => ({ name, qty: 1 })),
        amount: amount.trim() ? Number(amount) : null,
        currency: currency.toUpperCase() || null,
      });
      setItemsText("");
      setDeliveryDate("");
      setAmount("");
      setAdding(false);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="card">
      {customer.orders.length === 0 && !adding && <p className="muted small">No orders yet.</p>}
      {customer.orders.map((o) => (
        <OrderRow key={o.id} customerId={customer.id} order={o} onChanged={onChanged} />
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
            <div>
              <label htmlFor="new-order-items">Items</label>
              <input id="new-order-items" value={itemsText} onChange={(e) => setItemsText(e.target.value)} placeholder="Rice, Generator (comma-separated)" />
            </div>
            <div>
              <label htmlFor="new-order-amount">Amount</label>
              <input id="new-order-amount" type="number" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </div>
            <div>
              <label htmlFor="new-order-currency">Currency</label>
              <input id="new-order-currency" value={currency} onChange={(e) => setCurrency(e.target.value)} />
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
