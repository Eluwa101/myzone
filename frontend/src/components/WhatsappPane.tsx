import { Copy, ExternalLink, MessageCircle, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { logWhatsappOpened } from "../api/customers";
import { errorMessage } from "../api/errorMessage";
import { draftWhatsapp, previewMessageBatch } from "../api/messaging";
import type { ComposerState } from "../hooks/useComposer";
import { findPlaceholders, isBlankHtml } from "../utils/composer";
import { buildWaLink, htmlToPlainText, plainTextToHtml } from "../utils/whatsapp";
import AssistantCard from "./AssistantCard";
import ErrorText from "./ErrorText";
import ImproveMenu from "./ImproveMenu";
import InfoTip from "./InfoTip";
import MergeTagPicker from "./MergeTagPicker";
import Pagination from "./Pagination";

const PAGE_SIZE = 10;

/** The WhatsApp half of the composer. It starts from the email's wording and shares
 * the same merge tags; edit it here and it keeps its own text (Reset goes back to
 * following the email). Each person's message is filled in on the server, a page of
 * recipients at a time, then opened in WhatsApp with the text already typed in.
 *
 * wa.me can't tell us whether the message was then sent, so opening a chat is logged
 * as "opened" - never as sent. */
export default function WhatsappPane({ composer }: { composer: ComposerState }) {
  const { recipients, whatsappRecipients, bodyHtml, whatsappText, whatsappOpened, setWhatsappOpened } = composer;
  const [page, setPage] = useState(1);
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [problems, setProblems] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [armed, setArmed] = useState(false);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const requestRef = useRef(0);

  const following = whatsappText === null;
  // what the message is built from: the email's body, or the text typed in this tab
  const sourceHtml = following ? bodyHtml : plainTextToHtml(whatsappText);
  const sourceIsBlank = following ? isBlankHtml(bodyHtml) : !whatsappText.trim();
  const editorValue = useMemo(() => (following ? htmlToPlainText(bodyHtml) : whatsappText), [following, bodyHtml, whatsappText]);

  const total = whatsappRecipients.length;
  const last = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const current = Math.min(page, last);
  const shown = whatsappRecipients.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);
  const shownKey = shown.map((r) => r.id).join(",");
  const single = total === 1;

  // new wording means nobody has been messaged with *this* text yet. Skip the first run,
  // or just switching tabs would wipe the "opened" marks.
  const lastSource = useRef(sourceHtml);
  useEffect(() => {
    if (lastSource.current === sourceHtml) return;
    lastSource.current = sourceHtml;
    setWhatsappOpened(new Set());
    setArmed(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceHtml]);

  // fill in merge tags for the people on this page. Debounced, so typing doesn't fire a call per
  // keystroke, and only the latest request may write - a slow reply for older text must not win.
  useEffect(() => {
    const requestId = ++requestRef.current;
    if (sourceIsBlank || shown.length === 0) {
      setTexts({});
      setProblems([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    const timer = setTimeout(() => {
      previewMessageBatch(shown.map((r) => r.id), "", sourceHtml)
        .then((res) => {
          if (requestId !== requestRef.current) return;
          setTexts(Object.fromEntries(res.previews.map((p) => [p.customer_id, htmlToPlainText(p.body_html)])));
          setProblems(res.problems);
          setError(null);
        })
        .catch((err) => requestId === requestRef.current && setError(errorMessage(err)))
        .finally(() => requestId === requestRef.current && setLoading(false));
    }, 400);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceHtml, shownKey, sourceIsBlank]);

  // anything that means this isn't really ready: tags the server couldn't fill, or [fill-in] holes
  const placeholders = findPlaceholders(following ? bodyHtml : (whatsappText ?? ""));
  const warnings = [
    ...(problems.length ? [`Merge tags that could not be filled: ${problems.join(", ")}`] : []),
    ...(placeholders.length ? [`Unfilled placeholders: ${placeholders.join(", ")}`] : []),
  ];

  function insertTag(tag: string) {
    const el = textareaRef.current;
    const base = editorValue;
    const start = el?.selectionStart ?? base.length;
    const end = el?.selectionEnd ?? base.length;
    composer.setWhatsappText(base.slice(0, start) + tag + base.slice(end));
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(start + tag.length, start + tag.length);
    });
  }

  async function onDraft(description: string): Promise<boolean> {
    const draft = await draftWhatsapp({
      description,
      segmentId: composer.segmentId,
      currentText: editorValue.trim() ? editorValue : null,
    });
    composer.setWhatsappText(draft.text); // it becomes WhatsApp's own wording; the email is untouched
    return true;
  }

  function open(recipient: (typeof shown)[number]) {
    const text = texts[recipient.id];
    if (loading || !text) {
      setError("The message is still being prepared - try again in a moment.");
      return;
    }
    const link = buildWaLink(recipient.digits, text);
    if (link.tooLong) {
      setError("This message is too long for a WhatsApp chat link - shorten it and try again.");
      return;
    }
    // same two-step confirm as the email Send button: the first click only arms it
    // when the message still has holes in it
    if (warnings.length > 0 && !armed) {
      setArmed(true);
      return;
    }
    setArmed(false);
    setError(null);
    window.open(link.url, "_blank", "noopener,noreferrer");
    logWhatsappOpened(recipient.id, text);
    setWhatsappOpened((prev) => new Set(prev).add(recipient.id));
  }

  async function copyNumbers() {
    try {
      await navigator.clipboard.writeText(whatsappRecipients.map((r) => `+${r.digits}`).join("\n"));
      setCopyStatus("Phone numbers copied.");
    } catch {
      setCopyStatus("Could not copy - select the list manually.");
    }
  }

  const count = recipients?.length ?? 0;

  return (
    <div className="card whatsapp-pane">
      <p className="small" style={{ margin: "0 0 6px" }}>
        <MessageCircle size={13} className="h3-icon" /> <b>WhatsApp</b> - {total} of {count} {count === 1 ? "has" : "have"} a usable number
      </p>
      {composer.unusablePhoneCount > 0 && (
        <p className="muted small">
          {composer.unusablePhoneCount} saved number{composer.unusablePhoneCount === 1 ? " is" : "s are"} unusable (no country code, too
          short, or not a number)
          {composer.countryCode ? "" : " - set a default country code in Settings to fix local-format numbers like 0801…"}.
        </p>
      )}

      {total === 0 ? (
        <p className="muted small">No one here has a usable phone number on file.</p>
      ) : (
        <>
          <AssistantCard
            hasContent={!!editorValue.trim()}
            noun="message"
            placeholderChange="e.g. make it shorter and friendlier, and mention they can collect after 4pm"
            placeholderNew="e.g. tell them their order is ready for collection and thank them for shopping with us"
            onSubmit={onDraft}
          />
          <label htmlFor="whatsapp-message">Message</label>
          <textarea
            id="whatsapp-message"
            ref={textareaRef}
            rows={5}
            value={editorValue}
            onChange={(e) => composer.setWhatsappText(e.target.value)}
            placeholder="Write your message, or write the email first and it appears here…"
          />
          <div className="row" style={{ alignItems: "center", flexWrap: "wrap" }}>
            <MergeTagPicker onInsert={insertTag} />
            <ImproveMenu
              channel="whatsapp"
              disabled={sourceIsBlank}
              current={() => ({ body: editorValue })}
              apply={({ body }) => composer.setWhatsappText(body)}
            />
            {following ? (
              <span className="muted small">
                Same as the email{" "}
                <InfoTip label="About the WhatsApp wording">
                  This starts as your email's wording. Edit it here to give WhatsApp its own - the email isn't changed.
                </InfoTip>
              </span>
            ) : (
              <button type="button" className="btn-ghost" onClick={composer.resetWhatsapp}>
                <RotateCcw size={13} /> Match the email again
              </button>
            )}
          </div>

          {warnings.map((warning) => (
            <p key={warning} className="tag-problems small">
              {warning}
            </p>
          ))}
          {warnings.length > 0 && <p className="muted small">Press Open twice to open the chat with these left in.</p>}
          <ErrorText message={error} />

          <div className="submissions-list">
            {shown.map((r) => {
              const text = texts[r.id];
              const link = text ? buildWaLink(r.digits, text) : null;
              return (
                <div key={r.id} className="wa-row">
                  <div className="row-between">
                    <span>
                      {r.name}
                      {whatsappOpened.has(r.id) && <span className="muted small"> · opened</span>}
                      <span className="muted small"> · +{r.digits}</span>
                    </span>
                    <button
                      type="button"
                      className={armed ? "btn-danger" : whatsappOpened.has(r.id) ? "" : "btn-primary"}
                      onClick={() => open(r)}
                      disabled={loading || !text}
                    >
                      <ExternalLink size={13} /> {armed ? "Open anyway?" : whatsappOpened.has(r.id) ? "Open again" : "Open WhatsApp"}
                    </button>
                  </div>
                  {link?.tooLong && <p className="tag-problems small">Too long to open as a chat link - shorten the message.</p>}
                  {text ? (
                    <details open={single} className="wa-preview">
                      <summary className="muted small">Message for {r.name.split(" ")[0]}</summary>
                      <pre className="small">{text}</pre>
                    </details>
                  ) : (
                    loading && <p className="muted small">Preparing personalized message…</p>
                  )}
                </div>
              );
            })}
          </div>
          <Pagination page={current} pageSize={PAGE_SIZE} total={total} onChange={setPage} />

          {total > 1 && (
            <div style={{ marginTop: 10 }}>
              <button type="button" className="btn-ghost" onClick={copyNumbers}>
                <Copy size={14} /> Copy {total} phone numbers
              </button>
              <InfoTip label="About group messages">
                WhatsApp can't open one chat for many people - open each chat above, or paste these numbers and the message into a
                broadcast list in the WhatsApp app.
              </InfoTip>
              {copyStatus && <span className="muted small"> {copyStatus}</span>}
            </div>
          )}
        </>
      )}
    </div>
  );
}
