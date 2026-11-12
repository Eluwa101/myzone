import { Lightbulb } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { SuggestedMergeTag } from "../api/messaging";

/** The handful of merge tags and ready-made blocks that fit the segment
 * being emailed (worked out on the server from the segment's own
 * filters/SQL), each with the reason it was suggested. */
export default function SuggestedTagPicker({ suggestions, onInsert }: { suggestions: SuggestedMergeTag[]; onInsert: (tag: string) => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  return (
    <div className="merge-tag-picker" ref={ref}>
      <button type="button" className="icon-btn small suggested-tags-btn" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <Lightbulb size={14} /> Suggested for this segment <span className="suggested-count">{suggestions.length}</span>
      </button>
      {open && (
        <div className="merge-tag-panel suggested-tags-panel">
          {suggestions.map((s) => (
            <button
              key={s.tag}
              type="button"
              className="merge-tag-option"
              onClick={() => {
                onInsert(s.tag);
                setOpen(false);
              }}
            >
              <span className="suggested-label">{s.label}</span>
              <span className="muted small suggested-reason">{s.reason}</span>
              {s.tag.includes("\n") || s.tag.length > 40 ? <code className="suggested-code">{s.tag}</code> : <code className="suggested-code inline">{s.tag}</code>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
