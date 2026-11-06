import { Check, ChevronRight, Trash2 } from "lucide-react";
import { useState } from "react";
import { deleteTransaction, updateTransaction } from "../api/customers";
import { errorMessage } from "../api/errorMessage";
import type { Transaction } from "../api/types";
import CurrencySelect from "./CurrencySelect";
import ErrorText from "./ErrorText";

function money(n: number): string {
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function TransactionRow({
  customerId,
  transaction,
  onChanged,
}: {
  customerId: string;
  transaction: Transaction;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [date, setDate] = useState(transaction.date);
  const [item, setItem] = useState(transaction.item);
  const [qty, setQty] = useState(String(transaction.qty));
  const [amount, setAmount] = useState(String(transaction.amount));
  const [currency, setCurrency] = useState(transaction.currency);
  const [error, setError] = useState<string | null>(null);
  const [armedDelete, setArmedDelete] = useState(false);
  const [busy, setBusy] = useState(false);

  function startEdit() {
    setDate(transaction.date);
    setItem(transaction.item);
    setQty(String(transaction.qty));
    setAmount(String(transaction.amount));
    setCurrency(transaction.currency);
    setArmedDelete(false);
    setError(null);
    setOpen(true);
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await updateTransaction(customerId, transaction.id, {
        date,
        item,
        qty: Number(qty) || 0,
        amount: Number(amount) || 0,
        currency,
      });
      setOpen(false);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!armedDelete) {
      setArmedDelete(true);
      return;
    }
    setBusy(true);
    try {
      await deleteTransaction(customerId, transaction.id);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button type="button" className="info-row" onClick={startEdit}>
        <div className="info-row-text">
          <div className="info-row-label">{transaction.item || "(no item)"}</div>
          <div className="info-row-value muted">
            {transaction.date} · qty {transaction.qty} · {transaction.currency} {money(transaction.amount)}
          </div>
        </div>
        <ChevronRight size={16} className="muted" />
      </button>
    );
  }

  return (
    <div className="info-row-editing">
      <div className="tx-edit-grid">
        <div>
          <label htmlFor={`tx-date-${transaction.id}`}>Date</label>
          <input id={`tx-date-${transaction.id}`} type="date" value={date} onChange={(e) => setDate(e.target.value)} autoFocus />
        </div>
        <div>
          <label htmlFor={`tx-item-${transaction.id}`}>Item</label>
          <input id={`tx-item-${transaction.id}`} value={item} onChange={(e) => setItem(e.target.value)} />
        </div>
        <div>
          <label htmlFor={`tx-qty-${transaction.id}`}>Qty</label>
          <input id={`tx-qty-${transaction.id}`} type="number" value={qty} onChange={(e) => setQty(e.target.value)} />
        </div>
        <div>
          <label htmlFor={`tx-amount-${transaction.id}`}>Amount</label>
          <input id={`tx-amount-${transaction.id}`} type="number" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </div>
        <div>
          <label htmlFor={`tx-currency-${transaction.id}`}>Currency</label>
          <CurrencySelect id={`tx-currency-${transaction.id}`} value={currency} onChange={setCurrency} />
        </div>
      </div>
      <ErrorText message={error} />
      <div className="row" style={{ marginTop: 10 }}>
        <button type="button" className="btn-primary" onClick={save} disabled={busy}>
          <Check size={15} /> Save
        </button>
        <button type="button" onClick={() => setOpen(false)} disabled={busy}>
          Cancel
        </button>
        <button type="button" className="btn-danger" onClick={remove} disabled={busy} style={{ marginLeft: "auto" }}>
          <Trash2 size={15} /> {armedDelete ? "Confirm?" : "Delete"}
        </button>
      </div>
    </div>
  );
}
