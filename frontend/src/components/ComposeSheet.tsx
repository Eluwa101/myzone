import { X } from "lucide-react";
import { lazy, Suspense, useEffect, useRef } from "react";
import type { Recipient } from "../hooks/useComposer";
import Spinner from "./Spinner";

// the composer pulls in the rich-text editor, so it only loads once a sheet is opened
const Composer = lazy(() => import("./Composer"));

/** A panel that slides in from the right to write a message without leaving the page
 * you're on - e.g. from a customer's record. Closes on Escape, the X, or a click outside. */
export default function ComposeSheet({
  open,
  onClose,
  title,
  recipients,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  recipients: Recipient[];
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden"; // the page behind shouldn't scroll under the sheet
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      previouslyFocused?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="sheet-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet-panel" role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} ref={panelRef}>
        <div className="sheet-head">
          <h2>{title}</h2>
          <button type="button" className="icon-btn btn-ghost" aria-label="Close" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        <Suspense fallback={<Spinner />}>
          <Composer embedded recipients={recipients} />
        </Suspense>
      </div>
    </div>
  );
}
