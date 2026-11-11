import { ClipboardList, Plus, Receipt, StickyNote, UserRound, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
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

const FAB_SIZE = 56;
const FAB_MARGIN = 8;
const FAB_POS_KEY = "myzone_fab_pos";

function loadFabPos(): { x: number; y: number } | null {
  try {
    const raw = localStorage.getItem(FAB_POS_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveFabPos(pos: { x: number; y: number }) {
  try {
    localStorage.setItem(FAB_POS_KEY, JSON.stringify(pos));
  } catch {
    /* private browsing / storage disabled - position just won't persist */
  }
}

function clampFabPos(x: number, y: number) {
  const maxX = window.innerWidth - FAB_SIZE - FAB_MARGIN;
  const maxY = window.innerHeight - FAB_SIZE - FAB_MARGIN;
  return { x: Math.min(Math.max(FAB_MARGIN, x), Math.max(FAB_MARGIN, maxX)), y: Math.min(Math.max(FAB_MARGIN, y), Math.max(FAB_MARGIN, maxY)) };
}

/** Global quick-create entry point, mirroring what the AI assistant can do
 * (create a customer, or log an order/transaction/note against one) as a
 * manual, form-based alternative reachable from any page. Draggable so it
 * can be moved off whatever it's covering on a given page/screen size -
 * position persists (per device) across pages and reloads. */
export default function QuickCreateFab() {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<Kind | null>(null);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(() => loadFabPos());
  const [dragging, setDragging] = useState(false);
  const fabRef = useRef<HTMLButtonElement>(null);
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number; moved: boolean } | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) setKind(null);
  }, [open]);

  // keep it on-screen if the viewport is resized/rotated after a drag
  useEffect(() => {
    function onResize() {
      setPos((p) => (p ? clampFabPos(p.x, p.y) : p));
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  function onPointerDown(e: React.PointerEvent<HTMLButtonElement>) {
    if (e.button !== undefined && e.button !== 0) return;
    const rect = fabRef.current!.getBoundingClientRect();
    dragRef.current = { startX: e.clientX, startY: e.clientY, origX: rect.left, origY: rect.top, moved: false };
    fabRef.current!.setPointerCapture(e.pointerId);
  }

  function onPointerMove(e: React.PointerEvent<HTMLButtonElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    const dx = e.clientX - drag.startX;
    const dy = e.clientY - drag.startY;
    if (!drag.moved && Math.hypot(dx, dy) > 6) {
      drag.moved = true;
      setDragging(true);
    }
    if (drag.moved) {
      setPos(clampFabPos(drag.origX + dx, drag.origY + dy));
    }
  }

  function onPointerUp(e: React.PointerEvent<HTMLButtonElement>) {
    const drag = dragRef.current;
    dragRef.current = null;
    fabRef.current?.releasePointerCapture(e.pointerId);
    if (drag?.moved) {
      setDragging(false);
      setPos((p) => {
        if (p) saveFabPos(p);
        return p;
      });
    } else {
      setOpen((o) => !o);
    }
  }

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
      <button
        ref={fabRef}
        type="button"
        className={`fab quick-create-fab${dragging ? " fab-dragging" : ""}`}
        aria-label="Quick create (drag to move)"
        style={pos ? { left: pos.x, top: pos.y, right: "auto", bottom: "auto" } : undefined}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
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
