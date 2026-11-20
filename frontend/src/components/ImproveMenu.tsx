import { Heart, ListChecks, Scissors, Sparkles, Undo2, Wand2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { errorMessage } from "../api/errorMessage";
import { rewriteMessage, type RewriteAction } from "../api/messaging";
import InfoTip from "./InfoTip";

export interface MessageText {
  subject?: string | null;
  body: string;
}

/** "✨ Improve": shorten, tidy up, warm up or rewrite the message that's already written -
 * for either channel. Merge tags stay exactly as written (the server checks it, and hands the
 * original back with a warning rather than a damaged message) unless the person switches that
 * off. The change is applied straight away, with one-step Undo. */
export default function ImproveMenu({
  channel,
  current,
  apply,
  disabled,
}: {
  channel: "email" | "whatsapp";
  /** the message as it is right now - read when an action is picked */
  current: () => MessageText;
  /** put a message into the editor */
  apply: (next: MessageText) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [keepTags, setKeepTags] = useState(true);
  const [rewriting, setRewriting] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<{ text: string; warning: boolean } | null>(null);
  const [undo, setUndo] = useState<MessageText | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function run(action: RewriteAction, text?: string) {
    const before = current();
    if (!before.body.trim()) return;
    setOpen(false);
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      const res = await rewriteMessage({ channel, action, body: before.body, subject: before.subject ?? null, instruction: text, keepMergeTags: keepTags });
      if (res.warning) {
        setNote({ text: res.warning, warning: true });
      } else if (res.unchanged) {
        setNote({ text: "Nothing to change - it already reads that way.", warning: false });
      } else {
        apply({ subject: res.subject, body: res.body });
        setUndo(before);
        setNote({ text: keepTags ? "Updated - merge tags kept as written." : "Updated.", warning: false });
      }
      setRewriting(false);
      setInstruction("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const reformatLabel = channel === "whatsapp" ? "Format for WhatsApp" : "Tidy the formatting";

  return (
    <span className="improve" ref={wrapRef}>
      <span className="card-menu">
        <button type="button" disabled={disabled || busy} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          <Sparkles size={14} /> {busy ? "Improving…" : "Improve"}
        </button>
        {open && (
          <div className="card-menu-list improve-list" role="menu" style={{ right: "auto", left: 0 }}>
            <button type="button" role="menuitem" className="card-menu-item" onClick={() => run("shorten")}>
              <Scissors /> <span>Make it shorter</span>
            </button>
            <button type="button" role="menuitem" className="card-menu-item" onClick={() => run("friendlier")}>
              <Heart /> <span>Make it friendlier</span>
            </button>
            <button type="button" role="menuitem" className="card-menu-item" onClick={() => run("reformat")}>
              <ListChecks /> <span>{reformatLabel}</span>
            </button>
            <button type="button" role="menuitem" className="card-menu-item" onClick={() => setRewriting((r) => !r)} aria-expanded={rewriting}>
              <Wand2 /> <span>Rewrite it…</span>
            </button>
            {rewriting && (
              <form
                className="improve-rewrite"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (instruction.trim()) void run("rewrite", instruction.trim());
                }}
              >
                <input
                  autoFocus
                  aria-label="How should it change?"
                  placeholder="e.g. more formal, mention delivery"
                  value={instruction}
                  onChange={(e) => setInstruction(e.target.value)}
                />
                <button type="submit" className="btn-primary" disabled={!instruction.trim()}>
                  Rewrite
                </button>
              </form>
            )}
            <div className="card-menu-divider" role="separator" />
            <label className="improve-keep">
              <input type="checkbox" checked={keepTags} onChange={(e) => setKeepTags(e.target.checked)} />
              <span>Keep merge tags as they are</span>
              <InfoTip label="About keeping merge tags">
                On: every merge tag, link and [blank] comes back exactly as written, so the message still fills in per customer. Off: the
                assistant may reword around the tags or drop them.
              </InfoTip>
            </label>
          </div>
        )}
      </span>
      {undo && !busy && (
        <button
          type="button"
          className="btn-ghost"
          onClick={() => {
            apply(undo);
            setUndo(null);
            setNote(null);
          }}
        >
          <Undo2 size={13} /> Undo
        </button>
      )}
      {note && (
        <span className={note.warning ? "tag-problems small" : "muted small"} role={note.warning ? "alert" : "status"}>
          {note.text}
        </span>
      )}
      {error && (
        <span className="tag-problems small" role="alert">
          {error}
        </span>
      )}
    </span>
  );
}
