import { Info } from "lucide-react";
import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";

/** A small ⓘ that holds the explanatory text a screen doesn't need to show all the time.
 *
 *  - Mouse: opens on hover and on keyboard focus.
 *  - Touch / click: tap toggles it, tap elsewhere (or Escape) closes it.
 *  - Screen readers: the button is labelled and points at the tip with aria-describedby.
 *
 *  What belongs in one: how a feature works, why a limit exists, formatting hints.
 *  What does NOT: errors, warnings the person must act on, consent/unsubscribe rules that
 *  change what happens when they press a button, and destructive confirmations - those stay
 *  visible in the page. If missing it would cause a mistake, don't hide it. */
export default function InfoTip({ children, label = "More info" }: { children: ReactNode; label?: string }) {
  const id = useId();
  const wrapRef = useRef<HTMLSpanElement>(null);
  const tipRef = useRef<HTMLSpanElement>(null);
  const [hovered, setHovered] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [shift, setShift] = useState(0);
  const open = hovered || pinned;

  useEffect(() => {
    if (!pinned) return;
    function onDown(e: MouseEvent | TouchEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setPinned(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setPinned(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("touchstart", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("touchstart", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [pinned]);

  // keep the bubble on screen: nudge it back when it would run off either edge
  useLayoutEffect(() => {
    if (!open || !tipRef.current) return;
    tipRef.current.style.setProperty("--tip-shift", "0px");
    const rect = tipRef.current.getBoundingClientRect();
    const margin = 8;
    let delta = 0;
    if (rect.right > window.innerWidth - margin) delta = window.innerWidth - margin - rect.right;
    else if (rect.left < margin) delta = margin - rect.left;
    setShift(delta);
  }, [open]);

  return (
    <span
      className="infotip"
      ref={wrapRef}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <button
        type="button"
        className="infotip-btn"
        aria-label={label}
        aria-describedby={open ? id : undefined}
        aria-expanded={open}
        onClick={() => setPinned((p) => !p)}
        onFocus={() => setHovered(true)}
        onBlur={() => setHovered(false)}
      >
        <Info size={14} aria-hidden="true" />
      </button>
      {open && (
        <span id={id} role="tooltip" className="infotip-bubble" ref={tipRef} style={{ ["--tip-shift" as string]: `${shift}px` }}>
          {children}
        </span>
      )}
    </span>
  );
}
