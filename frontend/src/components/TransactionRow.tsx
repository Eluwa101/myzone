import { Check, ChevronRight, Trash2 } from "lucide-react";
import { useState } from "react";
import { deleteTransaction, updateTransaction } from "../api/customers";
import { errorMessage } from "../api/errorMessage";
import type { Transaction } from "../api/types";
import CurrencySelect from "./CurrencySelect";
import ErrorText from "./ErrorText";
import TransactionLinesEditor, { type TransactionLine } from "./TransactionLinesEditor";

function money(n: number): string {
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function itemsToText(items: Transaction["items"]): string {
  return items.map((i) => (i.qty && i.qty !== 1 ? `${i.item} x${i.qty}` : i.item)).join(", ");
}

function toLines(items: Transaction["items"]): TransactionLine[] {
  return items.map((i) => ({ item: i.item, qty: String(i.qty), amount: String(i.amount) }));
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
  const [lines, setLines] = useState<TransactionLine[]>(toLines(transaction.items));
  const [currency, setCurrency] = useState(transaction.currency);
  const [error, setError] = useState<string | null>(null);
  const [armedDelete, setArmedDelete] = useState(false);
  const [busy, setBusy] = useState(false);

  function startEdit() {
    setDate(transaction.date);
    setLines(toLines(transaction.items));
    setCurrency(transaction.currency);
    setArmedDelete(false);
    setError(null);
    setOpen(true);
  }

  async function save() {
    const cleanLines = lines.filter((l) => l.item.trim());
    if (cleanLines.length === 0) {
      setError("Add at least one item.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await updateTransaction(customerId, transaction.id, {
        date,
        items: cleanLines.map((l) => ({ item: l.item.trim(), qty: Number(l.qty) || 1, amount: Number(l.amount) || 0 })),
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
          <div className="info-row-label">{itemsToText(transaction.items) || "(no items)"}</div>
          <div className="info-row-value muted">
            {transaction.date} · {transaction.currency} {money(transaction.amount)}
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
          <label htmlFor={`tx-currency-${transaction.id}`}>Currency</label>
          <CurrencySelect id={`tx-currency-${transaction.id}`} value={currency} onChange={setCurrency} />
        </div>
      </div>
      <label>Items</label>
      <TransactionLinesEditor lines={lines} onChange={setLines} />
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
