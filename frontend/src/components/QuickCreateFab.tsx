import { ClipboardList, Plus, Receipt, StickyNote, UserRound, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listCustomers } from "../api/customers";
import type { Customer } from "../api/types";

type Kind = "customer" | "order" | "transaction" | "note";

const KINDS: { kind: Kind; label: string; Icon: typeof UserRound }[] = [
  { kind: "customer", label: "New customer", Icon: UserRound },
  { kind: "order", label: "New order", Icon: ClipboardList },
  { kind: "transaction", label: "New transaction", Icon: Receipt },
  { kind: "note", label: "New note", Icon: StickyNote },
];

/** Global quick-create entry point, mirroring what the AI assistant can do
 * (create a customer, or log an order/transaction/note against one) as a
 * manual, form-based alternative reachable from any page. */
export default function QuickCreateFab() {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<Kind | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) setKind(null);
  }, [open]);

  function close() {
    setOpen(false);
  }

  function pick(k: Kind) {
    if (k === "customer") {
      close();
      navigate("/customers/new");
      return;
    }
    setKind(k);
  }

  function onPickCustomer(customerId: string) {
    close();
    if (kind === "note") {
      navigate(`/notes?customer_id=${customerId}`);
    } else {
      navigate(`/customers/${customerId}?tab=${kind === "order" ? "orders" : "transactions"}&new=1`);
    }
  }

  return (
    <>
      {open && <div className="quick-create-backdrop" onClick={close} />}
      <button type="button" className="fab quick-create-fab" aria-label="Quick create" onClick={() => setOpen((o) => !o)}>
        <Plus size={24} strokeWidth={2.5} />
      </button>
      {open && (
        <div className="quick-create-sheet">
          <div className="quick-create-sheet-header">
            <h3>{kind ? "Pick a customer" : "Quick create"}</h3>
            <button type="button" className="icon-btn btn-ghost" aria-label="Close" onClick={close}>
              <X size={16} />
            </button>
          </div>
          {!kind ? (
            <div className="quick-create-grid">
              {KINDS.map(({ kind: k, label, Icon }) => (
                <button key={k} type="button" className="quick-create-option" onClick={() => pick(k)}>
                  <Icon size={20} />
                  {label}
                </button>
              ))}
            </div>
          ) : (
            <CustomerPicker onPick={onPickCustomer} onCancel={() => setKind(null)} />
          )}
        </div>
      )}
    </>
  );
}

function CustomerPicker({ onPick, onCancel }: { onPick: (customerId: string) => void; onCancel: () => void }) {
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const handle = setTimeout(() => {
      setLoading(true);
      listCustomers({ search, pageSize: 8 })
        .then((r) => setResults(r.items))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(handle);
  }, [search]);

  return (
    <div>
      <input
        autoFocus
        aria-label="Search customers"
        className="search-input"
        placeholder="Search customer by name, phone, email…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <div className="quick-create-results">
        {loading && <p className="muted small">Searching…</p>}
        {!loading && results.length === 0 && <p className="muted small">No customers found.</p>}
        {!loading &&
          results.map((c) => (
            <button key={c.id} type="button" className="quick-create-result" onClick={() => onPick(c.id)}>
              {c.name}
            </button>
          ))}
      </div>
      <button type="button" className="btn-ghost" onClick={onCancel} style={{ marginTop: 8 }}>
        Back
      </button>
    </div>
  );
}
