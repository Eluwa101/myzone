import { Plus, Trash2 } from "lucide-react";

export interface TransactionLine {
  item: string;
  qty: string;
  amount: string;
}

export function blankLine(): TransactionLine {
  return { item: "", qty: "1", amount: "" };
}

export function linesTotal(lines: TransactionLine[]): number {
  return lines.reduce((sum, l) => sum + (Number(l.amount) || 0), 0);
}

export default function TransactionLinesEditor({
  lines,
  onChange,
}: {
  lines: TransactionLine[];
  onChange: (lines: TransactionLine[]) => void;
}) {
  function update(i: number, patch: Partial<TransactionLine>) {
    onChange(lines.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  }
  function remove(i: number) {
    onChange(lines.filter((_, idx) => idx !== i));
  }
  function add() {
    onChange([...lines, blankLine()]);
  }

  return (
    <div className="order-items-editor">
      {lines.map((l, i) => (
        <div key={i} className="order-item-row">
          <input aria-label="Item" placeholder="Item" value={l.item} onChange={(e) => update(i, { item: e.target.value })} autoFocus={i === 0} />
          <input
            aria-label="Quantity"
            type="number"
            min={0}
            placeholder="Qty"
            value={l.qty}
            onChange={(e) => update(i, { qty: e.target.value })}
          />
          <input
            aria-label="Amount"
            type="number"
            min={0}
            step="0.01"
            placeholder="Amount"
            value={l.amount}
            onChange={(e) => update(i, { amount: e.target.value })}
          />
          {lines.length > 1 && (
            <button type="button" className="icon-btn btn-ghost" onClick={() => remove(i)} aria-label="Remove line">
              <Trash2 size={14} />
            </button>
          )}
        </div>
      ))}
      <button type="button" className="icon-btn btn-ghost" onClick={add}>
        <Plus size={14} /> Add another line
      </button>
      {lines.length > 1 && (
        <div className="row-between muted small" style={{ marginTop: 6 }}>
          <span>Lines total</span>
          <span>{linesTotal(lines).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
        </div>
      )}
    </div>
  );
}
