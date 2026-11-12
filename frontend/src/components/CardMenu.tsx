import { MoreHorizontal } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

export type MenuItem =
  | {
      key: string;
      label: string;
      icon?: ReactNode;
      /** runs when picked; the menu closes afterwards unless keepOpen */
      onSelect?: () => void | Promise<void>;
      /** navigates instead of running onSelect */
      to?: string;
      /** opens in a new tab instead of running onSelect */
      href?: string;
      danger?: boolean;
      /** a risky item asks once more first: the label changes to this text
       * and the menu stays open until it's picked again */
      confirm?: string;
      keepOpen?: boolean;
      disabled?: boolean;
      hidden?: boolean;
    }
  | { key: string; divider: true; hidden?: boolean };

/** The "⋯" button that opens a small menu of a card's less-used actions,
 * so the card itself stays clean. Closes on outside click or Escape, and
 * the items can be walked with the arrow keys. */
export default function CardMenu({ items, label = "More options" }: { items: MenuItem[]; label?: string }) {
  const [open, setOpen] = useState(false);
  const [armed, setArmed] = useState<string | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  function close() {
    setOpen(false);
    setArmed(null);
  }

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) close();
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        close();
        wrapRef.current?.querySelector<HTMLButtonElement>(".card-menu-btn")?.focus();
      }
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // listens on the whole menu (button + list), so ArrowDown straight after
  // opening it moves focus to the first item
  function onMenuKeys(e: React.KeyboardEvent) {
    if (!open || (e.key !== "ArrowDown" && e.key !== "ArrowUp")) return;
    const buttons = Array.from(menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]:not(:disabled)') ?? []);
    if (buttons.length === 0) return;
    e.preventDefault();
    const at = buttons.indexOf(document.activeElement as HTMLElement);
    let next: number;
    if (at === -1) next = e.key === "ArrowDown" ? 0 : buttons.length - 1;
    else next = e.key === "ArrowDown" ? (at + 1) % buttons.length : (at - 1 + buttons.length) % buttons.length;
    buttons[next].focus();
  }

  async function pick(item: Exclude<MenuItem, { divider: true }>) {
    if (item.confirm && armed !== item.key) {
      setArmed(item.key);
      return;
    }
    if (!item.keepOpen) close();
    await item.onSelect?.();
  }

  const visible = items.filter((i) => !i.hidden);
  if (visible.length === 0) return null;

  return (
    <div className="card-menu" ref={wrapRef} onKeyDown={onMenuKeys}>
      <button
        type="button"
        className="card-menu-btn"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => {
          setOpen((o) => !o);
          setArmed(null);
        }}
      >
        <MoreHorizontal size={18} />
      </button>
      {open && (
        <div className="card-menu-list" role="menu" ref={menuRef}>
          {visible.map((item) => {
            if ("divider" in item) return <div key={item.key} className="card-menu-divider" role="separator" />;
            const isArmed = armed === item.key;
            const className = `card-menu-item${item.danger ? " danger" : ""}${isArmed ? " armed" : ""}`;
            const content = (
              <>
                {item.icon}
                <span>{isArmed && item.confirm ? item.confirm : item.label}</span>
              </>
            );
            if (item.to) {
              return (
                <Link key={item.key} to={item.to} role="menuitem" className={className} onClick={close}>
                  {content}
                </Link>
              );
            }
            if (item.href) {
              return (
                <a key={item.key} href={item.href} target="_blank" rel="noreferrer" role="menuitem" className={className} onClick={close}>
                  {content}
                </a>
              );
            }
            return (
              <button key={item.key} type="button" role="menuitem" className={className} disabled={item.disabled} onClick={() => pick(item)}>
                {content}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
