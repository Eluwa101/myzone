import { Check, ChevronRight, Trash2 } from "lucide-react";
import { useState } from "react";
import { deleteOrder, updateOrder } from "../api/customers";
import { errorMessage } from "../api/errorMessage";
import type { Order } from "../api/types";
import ErrorText from "./ErrorText";

function itemsToText(items: Order["items"]): string {
  return items.map((i) => (i.qty && i.qty !== 1 ? `${i.name} x${i.qty}` : i.name)).join(", ");
}

function parseItems(text: string): Order["items"] {
  return text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((name) => ({ name, qty: 1 }));
}

export default function OrderRow({
  customerId,
  order,
  onChanged,
}: {
  customerId: string;
  order: Order;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [orderDate, setOrderDate] = useState(order.order_date);
  const [deliveryDate, setDeliveryDate] = useState(order.delivery_date ?? "");
  const [itemsText, setItemsText] = useState(itemsToText(order.items));
  const [amount, setAmount] = useState(order.amount != null ? String(order.amount) : "");
  const [currency, setCurrency] = useState(order.currency ?? "");
  const [paid, setPaid] = useState(order.paid);
  const [delivered, setDelivered] = useState(order.delivered);
  const [error, setError] = useState<string | null>(null);
  const [armedDelete, setArmedDelete] = useState(false);
  const [busy, setBusy] = useState(false);

  function startEdit() {
    setOrderDate(order.order_date);
    setDeliveryDate(order.delivery_date ?? "");
    setItemsText(itemsToText(order.items));
    setAmount(order.amount != null ? String(order.amount) : "");
    setCurrency(order.currency ?? "");
    setPaid(order.paid);
    setDelivered(order.delivered);
    setArmedDelete(false);
    setError(null);
    setOpen(true);
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await updateOrder(customerId, order.id, {
        order_date: orderDate,
        delivery_date: deliveryDate || null,
        items: parseItems(itemsText),
        amount: amount.trim() ? Number(amount) : null,
        currency: currency.toUpperCase() || null,
        paid,
        delivered,
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
      await deleteOrder(customerId, order.id);
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
          <div className="info-row-label">{itemsToText(order.items) || "(no items)"}</div>
          <div className="info-row-value muted">
            Ordered {order.order_date}
            {order.delivery_date ? ` · due ${order.delivery_date}` : ""}
            {" · "}
            {order.paid ? "Paid" : "Unpaid"} · {order.delivered ? "Delivered" : "Pending delivery"}
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
          <label htmlFor={`order-date-${order.id}`}>Order date</label>
          <input id={`order-date-${order.id}`} type="date" value={orderDate} onChange={(e) => setOrderDate(e.target.value)} autoFocus />
        </div>
        <div>
          <label htmlFor={`order-delivery-${order.id}`}>Delivery date</label>
          <input id={`order-delivery-${order.id}`} type="date" value={deliveryDate} onChange={(e) => setDeliveryDate(e.target.value)} />
        </div>
        <div>
          <label htmlFor={`order-items-${order.id}`}>Items</label>
          <input id={`order-items-${order.id}`} value={itemsText} onChange={(e) => setItemsText(e.target.value)} placeholder="Rice, Generator (comma-separated)" />
        </div>
        <div>
          <label htmlFor={`order-amount-${order.id}`}>Amount</label>
          <input id={`order-amount-${order.id}`} type="number" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </div>
        <div>
          <label htmlFor={`order-currency-${order.id}`}>Currency</label>
          <input id={`order-currency-${order.id}`} value={currency} onChange={(e) => setCurrency(e.target.value)} />
        </div>
      </div>
      <div className="row" style={{ marginTop: 10, gap: 16 }}>
        <label className="row" style={{ gap: 6 }}>
          <input type="checkbox" checked={paid} onChange={(e) => setPaid(e.target.checked)} /> Paid
        </label>
        <label className="row" style={{ gap: 6 }}>
          <input type="checkbox" checked={delivered} onChange={(e) => setDelivered(e.target.checked)} /> Delivered
        </label>
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
