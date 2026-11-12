import { Tag } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { listMergeTags, type MergeTag } from "../api/messaging";

/** Click a tag, it's inserted wherever the cursor currently is in the
 * compose field - fetches the catalog from the backend so this can never
 * drift out of sync with what the resolver actually understands. */
export default function MergeTagPicker({ onInsert }: { onInsert: (tag: string) => void }) {
  const [open, setOpen] = useState(false);
  const [tags, setTags] = useState<MergeTag[] | null>(null);
  const [query, setQuery] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open && tags === null) {
      listMergeTags()
        .then(setTags)
        .catch(() => setTags([]));
    }
  }, [open, tags]);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function pick(tag: string) {
    onInsert(tag);
    setOpen(false);
  }

  const q = query.trim().toLowerCase();
  const visible = (tags ?? []).filter((t) => !q || t.label.toLowerCase().includes(q) || t.category_label.toLowerCase().includes(q));

  const grouped = visible.reduce<Record<string, { label: string; tags: MergeTag[] }>>((acc, t) => {
    (acc[t.category] ??= { label: t.category_label, tags: [] }).tags.push(t);
    return acc;
  }, {});

  return (
    <div className="merge-tag-picker" ref={ref}>
      <button type="button" className="icon-btn btn-ghost small" onClick={() => setOpen((o) => !o)}>
        <Tag size={14} /> Insert merge tag
      </button>
      {open && (
        <div className="merge-tag-panel">
          {tags === null ? (
            <p className="muted small">Loading…</p>
          ) : (
            <>
              <input
                className="merge-tag-search"
                aria-label="Search merge tags"
                placeholder="Search tags…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              {visible.length === 0 && <p className="muted small">No tags match.</p>}
              {Object.entries(grouped).map(([category, group]) => (
              <div key={category} className="merge-tag-group">
                <div className="muted small merge-tag-group-label">{group.label}</div>
                {category === "conditions" && (
                  <p className="muted small merge-tag-hint">
                    Shows text only to customers it applies to. Edit the condition, e.g. <code>&gt;= 3</code> or{" "}
                    <code>between 1000 and 5000</code>.
                  </p>
                )}
                {category === "lists" && (
                  <p className="muted small merge-tag-hint">
                    Inserts a block you can edit: change the word in quotes, the number of days, or add{" "}
                    <code>sort amount desc</code> / <code>limit 5</code>.
                  </p>
                )}
                {group.tags.map((t) => (
                  <button key={t.tag} type="button" className="merge-tag-option" onClick={() => pick(t.tag)}>
                    {t.label}
                  </button>
                ))}
              </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
