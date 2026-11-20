import { AlertTriangle, Send, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { errorMessage } from "../api/errorMessage";
import { draftEmail, previewMessage, sendEmail, type MessagePreview } from "../api/messaging";
import type { ComposerState } from "../hooks/useComposer";
import { findPlaceholders, isBlankHtml } from "../utils/composer";
import EmailBodyEditor, { type EmailBodyEditorHandle } from "./EmailBodyEditor";
import ErrorText from "./ErrorText";
import HtmlPreviewFrame from "./HtmlPreviewFrame";
import ImproveMenu from "./ImproveMenu";
import InfoTip from "./InfoTip";
import MergeTagPicker from "./MergeTagPicker";
import SuggestedTagPicker from "./SuggestedTagPicker";

/** The Email half of the composer: template, subject, body (visual or HTML), merge
 * tags, the assistant, preview and send. Reads and writes the shared draft, so
 * whatever is written here is what the WhatsApp tab starts from.
 *
 * `embedded` drops the card chrome so it can sit inside another card. */
export default function EmailPane({ composer, embedded = false }: { composer: ComposerState; embedded?: boolean }) {
  const { recipients, subject, setSubject, bodyHtml, setBodyHtml, templateId, templates, suggestions } = composer;
  const [previewFor, setPreviewFor] = useState<MessagePreview | null>(null);
  const [draftPrompt, setDraftPrompt] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [previewIndex, setPreviewIndex] = useState(0);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeField, setActiveField] = useState<"subject" | "body">("body");
  const [armedSend, setArmedSend] = useState(false);

  const subjectRef = useRef<HTMLInputElement>(null);
  const editorRef = useRef<EmailBodyEditorHandle>(null);

  const count = recipients?.length ?? 0;
  const hasBody = !isBlankHtml(bodyHtml);
  const placeholders = findPlaceholders(subject, bodyHtml);
  const previewRecipient = recipients && count > 0 ? recipients[Math.min(previewIndex, count - 1)] : null;

  // a different template means a different email - the old preview no longer applies
  useEffect(() => setPreviewFor(null), [templateId]);
  useEffect(() => setArmedSend(false), [subject, bodyHtml]);

  async function onDraft() {
    if (!draftPrompt.trim()) return;
    setDrafting(true);
    setDraftError(null);
    try {
      const draft = await draftEmail({
        description: draftPrompt.trim(),
        segment_id: composer.segmentId,
        format: composer.draftFormat,
        current_subject: subject || null,
        current_body: hasBody ? bodyHtml : null,
      });
      setSubject(draft.subject);
      setBodyHtml(draft.body_html);
      composer.bumpEditor();
      setDraftPrompt("");
      setPreviewFor(null);
      const first = recipients?.[0];
      if (first) {
        setPreviewIndex(0);
        previewMessage(first.id, draft.subject, draft.body_html)
          .then(setPreviewFor)
          .catch(() => {});
      }
    } catch (err) {
      setDraftError(errorMessage(err));
    } finally {
      setDrafting(false);
    }
  }

  function insertTag(tag: string) {
    if (activeField === "subject" && subjectRef.current) {
      const el = subjectRef.current;
      const start = el.selectionStart ?? subject.length;
      const end = el.selectionEnd ?? subject.length;
      setSubject(subject.slice(0, start) + tag + subject.slice(end));
      requestAnimationFrame(() => {
        el.focus();
        el.setSelectionRange(start + tag.length, start + tag.length);
      });
    } else {
      editorRef.current?.insertTextAtCursor(tag);
    }
  }

  async function onPreview(index = previewIndex) {
    const target = recipients?.[index];
    if (!target) return;
    setPreviewIndex(index);
    setPreviewLoading(true);
    setError(null);
    try {
      setPreviewFor(await previewMessage(target.id, subject, bodyHtml));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPreviewLoading(false);
    }
  }

  async function onSend() {
    if (!recipients || count === 0 || !subject.trim() || !bodyHtml.trim()) return;
    if (placeholders.length > 0 && !armedSend) {
      setArmedSend(true);
      return;
    }
    setArmedSend(false);
    setSending(true);
    setError(null);
    setResult(null);
    try {
      const res = await sendEmail({
        customer_ids: recipients.map((r) => r.id),
        subject,
        body_html: bodyHtml,
        template_id: templateId || null,
        skip_without_consent: composer.skipWithoutConsent,
      });
      const parts = [`Sending to ${res.queued} customer${res.queued === 1 ? "" : "s"}.`];
      if (res.skipped_no_email) parts.push(`${res.skipped_no_email} skipped (no email on file).`);
      if (res.skipped_no_consent) parts.push(`${res.skipped_no_consent} skipped (no recorded consent).`);
      if (res.skipped_unsubscribed) parts.push(`${res.skipped_unsubscribed} skipped (unsubscribed).`);
      setResult(parts.join(" "));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSending(false);
    }
  }

  const section = embedded ? "composer-section" : "card";

  return (
    <div className="email-composer">
      <div className="card assistant-suggest-card">
        <label htmlFor="draft-prompt">
          <Sparkles size={13} className="h3-icon" />{" "}
          {hasBody ? "Describe a change, and the assistant will rewrite the email" : "Describe the email, and the assistant will write it"}
        </label>
        <textarea
          id="draft-prompt"
          rows={2}
          value={draftPrompt}
          onChange={(e) => setDraftPrompt(e.target.value)}
          placeholder={
            hasBody
              ? "e.g. make it shorter, and add a line for anyone who hasn't paid their order"
              : "e.g. thank them for their lighter purchases, list each one with the date and total, and if they've bought 3 or more offer [discount] on gas"
          }
        />
        <div className="row" style={{ alignItems: "center" }}>
          <select
            aria-label="Email style"
            value={composer.draftFormat}
            onChange={(e) => composer.setDraftFormat(e.target.value as "simple" | "designed")}
            style={{ width: "auto" }}
          >
            <option value="simple">Simple text</option>
            <option value="designed">Designed (HTML layout)</option>
          </select>
          <button type="button" onClick={onDraft} disabled={drafting || !draftPrompt.trim()}>
            <Sparkles size={14} /> {drafting ? "Writing…" : hasBody ? "Rewrite" : "Write email"}
          </button>
        </div>
        <ErrorText message={draftError} />
      </div>

      <div className={section}>
        {!embedded && <h3>Template (optional)</h3>}
        {embedded && <label>Template (optional)</label>}
        <select aria-label="Choose a template" value={templateId} onChange={(e) => composer.selectTemplate(e.target.value)}>
          <option value="">Start from scratch</option>
          {templates.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </div>

      <div className={section}>
        {!embedded && <h3>Message</h3>}
        <label>Subject</label>
        <input
          aria-label="Subject"
          ref={subjectRef}
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          onFocus={() => setActiveField("subject")}
        />
        <label>Body</label>
        <div onFocus={() => setActiveField("body")}>
          {/* keyed on the template so a designed (table/CSS) template opens in HTML mode */}
          <EmailBodyEditor key={`${templateId}-${composer.editorVersion}`} ref={editorRef} value={bodyHtml} onChange={setBodyHtml} placeholder="Write your message…" />
        </div>
        <div className="row" style={{ marginTop: 10, alignItems: "center", flexWrap: "wrap" }}>
          {suggestions.length > 0 && <SuggestedTagPicker suggestions={suggestions} onInsert={insertTag} />}
          <MergeTagPicker onInsert={insertTag} />
          <ImproveMenu
            channel="email"
            disabled={!hasBody}
            current={() => ({ subject, body: bodyHtml })}
            apply={({ subject: nextSubject, body }) => {
              if (nextSubject != null) setSubject(nextSubject);
              setBodyHtml(body);
              composer.bumpEditor(); // reopen the editor on the new text
            }}
          />
        </div>
        <label className="row" style={{ gap: 6, marginTop: 10, alignItems: "center" }}>
          <input type="checkbox" checked={composer.skipWithoutConsent} onChange={(e) => composer.setSkipWithoutConsent(e.target.checked)} />
          Skip customers with no recorded consent
          <InfoTip label="About unsubscribing">
            An unsubscribe link is added to the bottom of every email, and anyone who unsubscribes is always skipped.
          </InfoTip>
        </label>
      </div>

      {previewFor && previewRecipient && (
        <div className={section}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            {embedded ? <b className="small">Preview</b> : <h3 style={{ margin: 0 }}>Preview</h3>}
            {count > 1 && (
              <span className="row" style={{ alignItems: "center", gap: 6 }}>
                <button type="button" className="small" disabled={previewLoading || previewIndex === 0} onClick={() => onPreview(previewIndex - 1)}>
                  ‹
                </button>
                <span className="muted small">
                  {previewIndex + 1} of {count}
                </span>
                <button type="button" className="small" disabled={previewLoading || previewIndex >= count - 1} onClick={() => onPreview(previewIndex + 1)}>
                  ›
                </button>
              </span>
            )}
          </div>
          <p className="muted small" style={{ margin: "6px 0" }}>
            As {previewRecipient.name} would see it
          </p>
          {previewFor.problems && previewFor.problems.length > 0 && (
            <div className="tag-problems" role="alert">
              <p className="small" style={{ margin: "0 0 4px" }}>
                <AlertTriangle size={13} className="h3-icon" /> <b>Some merge tags won't work yet:</b>
              </p>
              <ul className="small">
                {previewFor.problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </div>
          )}
          <p className="small">
            <b>{previewFor.subject}</b>
          </p>
          <HtmlPreviewFrame html={previewFor.body_html} />
        </div>
      )}

      {placeholders.length > 0 && (
        <div className="tag-problems" role="status">
          <p className="small" style={{ margin: 0 }}>
            <AlertTriangle size={13} className="h3-icon" /> <b>Fill in before sending:</b> {placeholders.join(", ")} - every customer
            would see {placeholders.length === 1 ? "it" : "them"} exactly as written.
          </p>
        </div>
      )}

      <ErrorText message={error} />
      {result && <p className="muted small page-note">{result}</p>}

      <div className="row" style={{ margin: embedded ? "12px 0 0" : "12px 0 24px" }}>
        <button type="button" onClick={() => onPreview()} disabled={previewLoading || count === 0}>
          {previewLoading ? "Loading…" : "Preview"}
        </button>
        <button
          type="button"
          className={armedSend ? "btn-danger" : "btn-primary"}
          onClick={onSend}
          disabled={sending || count === 0 || !subject.trim() || !bodyHtml.trim()}
        >
          <Send size={15} />{" "}
          {sending ? "Sending…" : armedSend ? `Send with ${placeholders.join(", ")} in it?` : `Send${count > 1 ? ` to ${count}` : ""}`}
        </button>
      </div>
    </div>
  );
}
