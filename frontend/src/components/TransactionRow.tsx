import { useState } from "react";
import { deleteTransaction, updateTransaction } from "../api/customers";
import { errorMessage } from "../api/errorMessage";
import type { Transaction } from "../api/types";

export default function TransactionRow({
  customerId,
  transaction,
  onChanged,
}: {
  customerId: string;
  transaction: Transaction;
  onChanged: () => void;
}) {
  const [date, setDate] = useState(transaction.date);
  const [item, setItem] = useState(transaction.item);
  const [qty, setQty] = useState(String(transaction.qty));
  const [amount, setAmount] = useState(String(transaction.amount));
  const [currency, setCurrency] = useState(transaction.currency);
  const [error, setError] = useState<string | null>(null);
  const [armedDelete, setArmedDelete] = useState(false);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await updateTransaction(customerId, transaction.id, {
        date,
        item,
        qty: Number(qty) || 0,
        amount: Number(amount) || 0,
        currency: currency.toUpperCase(),
      });
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

  return (
    <div className="tx-row">
      <input aria-label="Date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
      <input aria-label="Item" placeholder="Item" value={item} onChange={(e) => setItem(e.target.value)} />
      <input aria-label="Quantity" type="number" placeholder="Qty" value={qty} onChange={(e) => setQty(e.target.value)} />
      <input aria-label="Amount" type="number" placeholder="Amount" value={amount} onChange={(e) => setAmount(e.target.value)} />
      <input aria-label="Currency" placeholder="Cur." value={currency} onChange={(e) => setCurrency(e.target.value)} />
      <div className="tx-row-actions">
        <button type="button" onClick={save} disabled={busy}>
          Save
        </button>
        <button type="button" className="btn-danger" onClick={remove} disabled={busy}>
          {armedDelete ? "Confirm?" : "Delete"}
        </button>
      </div>
      {error && <p className="error-text small">{error}</p>}
    </div>
  );
}
