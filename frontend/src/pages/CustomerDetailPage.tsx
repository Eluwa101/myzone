import { Plus, Trash2 } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  addTransaction,
  createCustomer,
  deleteCustomer,
  getCustomer,
  type CustomerInput,
  updateCustomer,
} from "../api/customers";
import { ApiError } from "../api/client";
import { errorMessage } from "../api/errorMessage";
import type { Customer, CustomerStatus } from "../api/types";
import ErrorText from "../components/ErrorText";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";
import TransactionRow from "../components/TransactionRow";

const BLANK: CustomerInput = { name: "" };

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

  // new-transaction draft
  const [txDate, setTxDate] = useState(new Date().toISOString().slice(0, 10));
  const [txItem, setTxItem] = useState("");
  const [txQty, setTxQty] = useState("1");
  const [txAmount, setTxAmount] = useState("");
  const [txCurrency, setTxCurrency] = useState("");

  function loadCustomer() {
    if (!id || isNew) return;
    setLoading(true);
    getCustomer(id)
      .then((c) => {
        setCustomer(c);
        setForm({
          name: c.name,
          phone: c.phone ?? "",
          email: c.email ?? "",
          job: c.job ?? "",
          nationality: c.nationality ?? "",
          pet: c.pet ?? "",
          birthday: c.birthday ?? "",
          address: c.address ?? "",
          notes: c.notes ?? "",
          interests: c.interests ?? "",
          status: c.status,
          consent_date: c.consent_date ?? "",
        });
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }

  useEffect(loadCustomer, [id, isNew]);

  function set<K extends keyof CustomerInput>(key: K, value: CustomerInput[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function onSave(e: FormEvent, force = false) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setConflict(null);
    try {
      if (isNew) {
        const created = await createCustomer(form, force);
        navigate(`/customers/${created.id}`, { replace: true });
      } else if (id) {
        const updated = await updateCustomer(id, form);
        setCustomer(updated);
      }
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

  async function onDelete() {
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

  async function onAddTransaction(e: FormEvent) {
    e.preventDefault();
    if (!id || !txItem.trim()) return;
    setError(null);
    try {
      await addTransaction(id, {
        date: txDate,
        item: txItem.trim(),
        qty: Number(txQty) || 1,
        amount: Number(txAmount) || 0,
        currency: txCurrency.toUpperCase(),
      });
      setTxItem("");
      setTxAmount("");
      loadCustomer();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  if (loading) return <Spinner />;

  return (
    <div>
      <TopBar title={isNew ? "New customer" : form.name || "Customer"} />

      <form className="card" onSubmit={onSave}>
        <div className="form-grid">
          <div>
            <label htmlFor="cf-name">Full name *</label>
            <input id="cf-name" value={form.name} onChange={(e) => set("name", e.target.value)} required />
          </div>
          <div>
            <label htmlFor="cf-phone">Phone / WhatsApp</label>
            <input id="cf-phone" value={form.phone ?? ""} onChange={(e) => set("phone", e.target.value)} />
          </div>
          <div>
            <label htmlFor="cf-email">Email</label>
            <input id="cf-email" type="email" value={form.email ?? ""} onChange={(e) => set("email", e.target.value)} />
          </div>
          <div>
            <label htmlFor="cf-job">Job / occupation</label>
            <input id="cf-job" value={form.job ?? ""} onChange={(e) => set("job", e.target.value)} />
          </div>
          <div>
            <label htmlFor="cf-nationality">Nationality</label>
            <input id="cf-nationality" value={form.nationality ?? ""} onChange={(e) => set("nationality", e.target.value)} />
          </div>
          <div>
            <label htmlFor="cf-pet">Pet(s)</label>
            <input id="cf-pet" value={form.pet ?? ""} onChange={(e) => set("pet", e.target.value)} />
          </div>
          <div>
            <label htmlFor="cf-birthday">Birthday</label>
            <input id="cf-birthday" type="date" value={form.birthday ?? ""} onChange={(e) => set("birthday", e.target.value)} />
          </div>
          <div>
            <label htmlFor="cf-address">Address / city</label>
            <input id="cf-address" value={form.address ?? ""} onChange={(e) => set("address", e.target.value)} />
          </div>
          <div style={{ gridColumn: "1 / -1" }}>
            <label htmlFor="cf-interests">Interested in</label>
            <input
              id="cf-interests"
              value={form.interests ?? ""}
              onChange={(e) => set("interests", e.target.value)}
              placeholder="Generator, Rice (comma-separated)"
            />
          </div>
          <div>
            <label htmlFor="cf-status">Status</label>
            <select id="cf-status" value={form.status ?? ""} onChange={(e) => set("status", e.target.value as CustomerStatus)}>
              <option value="">Auto</option>
              <option value="lead">Lead</option>
              <option value="customer">Customer</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
          <div>
            <label htmlFor="cf-consent">Consent to be stored (date given)</label>
            <input id="cf-consent" type="date" value={form.consent_date ?? ""} onChange={(e) => set("consent_date", e.target.value)} />
          </div>
        </div>
        <label htmlFor="cf-notes">Notes</label>
        <textarea id="cf-notes" rows={2} value={form.notes ?? ""} onChange={(e) => set("notes", e.target.value)} />

        <ErrorText message={error} />
        {conflict && (
          <div className="card conflict-card">
            <p>{conflict.message}</p>
            <div className="row">
              <button type="button" onClick={() => navigate(`/customers/${conflict.existingId}`)}>
                View existing
              </button>
              <button type="button" className="btn-primary" onClick={(e) => onSave(e, true)}>
                Save as new anyway
              </button>
            </div>
          </div>
        )}

        <div className="row" style={{ marginTop: 12 }}>
          <button className="btn-primary" type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </button>
          {!isNew && (
            <button type="button" className="btn-danger" onClick={onDelete} disabled={saving} style={{ marginLeft: "auto" }}>
              <Trash2 size={15} />
              {armedDelete ? "Click again to confirm" : "Delete customer"}
            </button>
          )}
        </div>
      </form>

      {!isNew && customer && (
        <div className="card">
          <h3>Transactions</h3>
          {customer.transactions.map((t) => (
            <TransactionRow key={t.id} customerId={customer.id} transaction={t} onChanged={loadCustomer} />
          ))}
          <form className="tx-row" onSubmit={onAddTransaction}>
            <input aria-label="Date" type="date" value={txDate} onChange={(e) => setTxDate(e.target.value)} />
            <input aria-label="Item" placeholder="Item" value={txItem} onChange={(e) => setTxItem(e.target.value)} />
            <input aria-label="Quantity" type="number" placeholder="Qty" value={txQty} onChange={(e) => setTxQty(e.target.value)} />
            <input aria-label="Amount" type="number" placeholder="Amount" value={txAmount} onChange={(e) => setTxAmount(e.target.value)} />
            <input aria-label="Currency" placeholder="Cur." value={txCurrency} onChange={(e) => setTxCurrency(e.target.value)} />
            <button type="submit" className="icon-btn btn-primary" aria-label="Add transaction">
              <Plus size={15} />
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
