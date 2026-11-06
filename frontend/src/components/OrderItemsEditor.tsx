import { Plus, Trash2 } from "lucide-react";
import type { OrderItem } from "../api/types";

export function itemsTotal(items: OrderItem[]): number {
  return items.reduce((sum, it) => sum + (it.price ?? 0) * (it.qty || 1), 0);
}

export function hasPricedItems(items: OrderItem[]): boolean {
  return items.some((it) => it.price != null);
}

export default function OrderItemsEditor({ items, onChange }: { items: OrderItem[]; onChange: (items: OrderItem[]) => void }) {
  function update(i: number, patch: Partial<OrderItem>) {
    onChange(items.map((it, idx) => (idx === i ? { ...it, ...patch } : it)));
  }
  function remove(i: number) {
    onChange(items.filter((_, idx) => idx !== i));
  }
  function add() {
    onChange([...items, { name: "", qty: 1, price: null }]);
  }

  return (
    <div className="order-items-editor">
      {items.map((it, i) => (
        <div key={i} className="order-item-row">
          <input aria-label="Item name" placeholder="Item name" value={it.name} onChange={(e) => update(i, { name: e.target.value })} />
          <input
            aria-label="Quantity"
            type="number"
            min={0}
            placeholder="Qty"
            value={it.qty}
            onChange={(e) => update(i, { qty: Number(e.target.value) || 1 })}
          />
          <input
            aria-label="Price"
            type="number"
            min={0}
            step="0.01"
            placeholder="Price"
            value={it.price ?? ""}
            onChange={(e) => update(i, { price: e.target.value ? Number(e.target.value) : null })}
          />
          <span className="muted small order-item-subtotal">
            {it.price != null ? ((it.price ?? 0) * (it.qty || 1)).toLocaleString(undefined, { minimumFractionDigits: 2 }) : ""}
          </span>
          <button type="button" className="icon-btn btn-ghost" onClick={() => remove(i)} aria-label="Remove item">
            <Trash2 size={14} />
          </button>
        </div>
      ))}
      <button type="button" className="icon-btn btn-ghost" onClick={add}>
        <Plus size={14} /> Add item
      </button>
      {hasPricedItems(items) && (
        <div className="row-between muted small" style={{ marginTop: 6 }}>
          <span>Items total</span>
          <span>{itemsTotal(items).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
        </div>
      )}
    </div>
  );
}
