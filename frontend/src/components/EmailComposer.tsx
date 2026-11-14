import { AlertTriangle, MessageCircle, Send, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { errorMessage } from "../api/errorMessage";
import {
  draftEmail,
  listEmailTemplates,
  listSuggestedMergeTags,
  previewMessage,
  sendEmail,
  type EmailTemplate,
  type MessagePreview,
  type SuggestedMergeTag,
} from "../api/messaging";
import EmailBodyEditor, { looksLikeCustomHtml, type EmailBodyEditorHandle } from "./EmailBodyEditor";
import ErrorText from "./ErrorText";
import HtmlPreviewFrame from "./HtmlPreviewFrame";
import MergeTagPicker from "./MergeTagPicker";
import SuggestedTagPicker from "./SuggestedTagPicker";

/** Fill-in-the-blanks like [discount] - same rule as the backend's
 * find_placeholders, checked live so the warning shows while typing. */
function findPlaceholders(...texts: string[]): string[] {
  const decoder = document.createElement("textarea");
  const found: string[] = [];
  for (const text of texts) {
    decoder.innerHTML = text;
    for (const m of decoder.value.matchAll(/\[([A-Za-z][A-Za-z0-9 _\-/'&.]{0,40})\]/g)) {
      if (!found.includes(m[0])) found.push(m[0]);
    }
  }
  return found;
}

export interface Recipient {
  id: string;
  name: string;
  email: string | null;
  phone?: string | null;
}

function whatsappNumber(phone: string): string | null {
  const digits = phone.replace(/\D/g, "");
  return digits.length >= 8 && digits.length <= 15 && !digits.startsWith("0") ? digits : null;
}

function htmlToPlainText(html: string): string {
  const doc = new DOMParser().parseFromString(html, "text/html");
  doc.querySelectorAll("script, style, head, noscript").forEach((node) => node.remove());
  doc.querySelectorAll("br").forEach((node) => node.replaceWith(doc.createTextNode("\n")));
  doc.querySelectorAll("p, div, li, tr, h1, h2, h3, h4, blockquote").forEach((node) => node.append(doc.createTextNode("\n")));
  return (doc.body.textContent ?? "").replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
}

/** Everything about writing and sending one email to a set of customers -
 * template choice, subject, body (visual or HTML), merge tags, preview and
 * send - without deciding who the recipients are. The compose page and the
 * "Reach segment" panel both wrap this with their own recipient list.
 *
 * `embedded` drops the card chrome so it can sit inside another card. */
export default function EmailComposer({
  recipients,
  initialTemplateId,
  segmentId,
  embedded = false,
}: {
  recipients: Recipient[] | null;
  initialTemplateId?: string | null;
  /** when emailing a segment: suggests tags that fit it, and tells the assistant who it's writing to */
  segmentId?: string | null;
  embedded?: boolean;
}) {
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [templateId, setTemplateId] = useState("");
  const [subject, setSubject] = useState("");
  const [bodyHtml, setBodyHtml] = useState("");
  const [skipWithoutConsent, setSkipWithoutConsent] = useState(true);
  const [previewFor, setPreviewFor] = useState<MessagePreview | null>(null);
  const [suggestions, setSuggestions] = useState<SuggestedMergeTag[]>([]);
  const [draftPrompt, setDraftPrompt] = useState("");
  const [draftFormat, setDraftFormat] = useState<"simple" | "designed">("simple");
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  // bumped when the assistant replaces the body, so the editor reopens in
  // the right mode (a designed HTML email opens in HTML, not the visual editor)
  const [editorVersion, setEditorVersion] = useState(0);
  const [previewIndex, setPreviewIndex] = useState(0);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeField, setActiveField] = useState<"subject" | "body">("body");
  const [showWhatsapp, setShowWhatsapp] = useState(false);
  const [whatsappIndex, setWhatsappIndex] = useState(0);
  const [whatsappPreview, setWhatsappPreview] = useState<MessagePreview | null>(null);
  const [whatsappLoading, setWhatsappLoading] = useState(false);
  const [whatsappError, setWhatsappError] = useState<string | null>(null);

  const subjectRef = useRef<HTMLInputElement>(null);
  const editorRef = useRef<EmailBodyEditorHandle>(null);

  useEffect(() => {
    listEmailTemplates()
      .then((loaded) => {
        setTemplates(loaded);
        const preselect = initialTemplateId && loaded.find((t) => t.id === initialTemplateId);
        if (preselect) {
          setTemplateId(preselect.id);
          setSubject(preselect.subject);
          setBodyHtml(preselect.body_html);
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!segmentId) return;
    listSuggestedMergeTags(segmentId)
      .then(setSuggestions)
      .catch(() => setSuggestions([]));
  }, [segmentId]);

  async function onDraft() {
    if (!draftPrompt.trim()) return;
    setDrafting(true);
    setDraftError(null);
    try {
      const draft = await draftEmail({
        description: draftPrompt.trim(),
        segment_id: segmentId ?? null,
        format: draftFormat,
        current_subject: subject || null,
        current_body: bodyHtml.replace(/<[^>]*>|&nbsp;/g, "").trim() ? bodyHtml : null,
      });
      setSubject(draft.subject);
      setBodyHtml(draft.body_html);
      setEditorVersion((v) => v + 1);
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

  const hasBody = bodyHtml.replace(/<[^>]*>|&nbsp;/g, "").trim().length > 0;

  function onSelectTemplate(id: string) {
    setTemplateId(id);
    setPreviewFor(null);
    const t = templates.find((tpl) => tpl.id === id);
    if (t) {
      setSubject(t.subject);
      setBodyHtml(t.body_html);
      setDraftFormat(looksLikeCustomHtml(t.body_html) ? "designed" : "simple");
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

  const count = recipients?.length ?? 0;
  const whatsappRecipients = (recipients ?? []).filter((recipient) => recipient.phone && whatsappNumber(recipient.phone));
  const invalidPhoneCount = (recipients ?? []).filter((recipient) => recipient.phone && !whatsappNumber(recipient.phone)).length;
  const whatsappRecipient = whatsappRecipients[whatsappIndex] ?? null;
  const previewRecipient = recipients && count > 0 ? recipients[Math.min(previewIndex, count - 1)] : null;

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

  async function loadWhatsappPreview(index: number) {
    const target = whatsappRecipients[index];
    if (!target) return;
    setWhatsappIndex(index);
    setWhatsappLoading(true);
    setWhatsappError(null);
    try {
      setWhatsappPreview(await previewMessage(target.id, subject, bodyHtml));
    } catch (err) {
      setWhatsappError(errorMessage(err));
    } finally {
      setWhatsappLoading(false);
    }
  }

  function openWhatsapp() {
    if (whatsappLoading || !whatsappRecipient || !whatsappPreview) return;
    const phone = whatsappNumber(whatsappRecipient.phone ?? "");
    const message = htmlToPlainText(whatsappPreview.body_html);
    if (!phone || !message) {
      setWhatsappError("This customer does not have a usable phone number or message.");
      return;
    }
    window.open(`https://wa.me/${phone}?text=${encodeURIComponent(message)}`, "_blank", "noopener,noreferrer");
  }

  useEffect(() => {
    if (!showWhatsapp) return;
    setWhatsappPreview(null);
    setWhatsappIndex(0);
    if (whatsappRecipients.length) void loadWhatsappPreview(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showWhatsapp, subject, bodyHtml, recipients]);

  const placeholders = findPlaceholders(subject, bodyHtml);
  const [armedSend, setArmedSend] = useState(false);
  useEffect(() => setArmedSend(false), [subject, bodyHtml]);

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
        skip_without_consent: skipWithoutConsent,
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
          <select aria-label="Email style" value={draftFormat} onChange={(e) => setDraftFormat(e.target.value as "simple" | "designed")} style={{ width: "auto" }}>
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
        <select aria-label="Choose a template" value={templateId} onChange={(e) => onSelectTemplate(e.target.value)}>
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
          <EmailBodyEditor key={`${templateId}-${editorVersion}`} ref={editorRef} value={bodyHtml} onChange={setBodyHtml} placeholder="Write your message…" />
        </div>
        <div className="row" style={{ marginTop: 10 }}>
          {suggestions.length > 0 && <SuggestedTagPicker suggestions={suggestions} onInsert={insertTag} />}
          <MergeTagPicker onInsert={insertTag} />
        </div>
        <label className="row" style={{ gap: 6, marginTop: 10 }}>
          <input type="checkbox" checked={skipWithoutConsent} onChange={(e) => setSkipWithoutConsent(e.target.checked)} />
          Skip customers with no recorded consent
        </label>
        <p className="muted small" style={{ margin: "4px 0 0" }}>
          An unsubscribe link is added to the bottom of every email, and anyone who unsubscribes is always skipped.
        </p>
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
        <button type="button" onClick={() => setShowWhatsapp((open) => !open)} disabled={whatsappRecipients.length === 0 || !bodyHtml.trim()}>
          <MessageCircle size={15} /> WhatsApp{whatsappRecipients.length > 0 ? ` (${whatsappRecipients.length})` : ""}
        </button>
      </div>

      {showWhatsapp && (
        <div className={section}>
          <h3>Open a WhatsApp chat</h3>
          <p className="muted small">The message uses this draft with merge tags filled in for each customer. Review and send it in WhatsApp.</p>
          <p className="muted small">
            {whatsappRecipients.length} of {count} customers have a usable international phone number
            {invalidPhoneCount ? `; ${invalidPhoneCount} saved number${invalidPhoneCount === 1 ? " is" : "s are"} not in international format` : ""}.
          </p>
          {whatsappRecipient && (
            <div className="row" style={{ alignItems: "center", flexWrap: "wrap" }}>
              <label htmlFor="whatsapp-recipient">Customer</label>
              <select id="whatsapp-recipient" value={whatsappIndex} onChange={(event) => void loadWhatsappPreview(Number(event.target.value))}>
                {whatsappRecipients.map((recipient, index) => (
                  <option key={recipient.id} value={index}>{recipient.name} · {recipient.phone}</option>
                ))}
              </select>
              {whatsappRecipients.length > 1 && <span className="muted small">{whatsappIndex + 1} of {whatsappRecipients.length}</span>}
              <button type="button" className="btn-primary" onClick={openWhatsapp} disabled={whatsappLoading || !whatsappPreview}>
                <MessageCircle size={15} /> Open WhatsApp
              </button>
            </div>
          )}
          {whatsappLoading && <p className="muted small">Preparing personalized message…</p>}
          {whatsappPreview && whatsappRecipient && <pre className="small" style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{htmlToPlainText(whatsappPreview.body_html)}</pre>}
          {whatsappError && <ErrorText message={whatsappError} />}
          {whatsappPreview?.problems?.length ? <p className="tag-problems small">Some merge tags could not be filled: {whatsappPreview.problems.join(", ")}</p> : null}
          {placeholders.length > 0 && <p className="tag-problems small">Fill these placeholders before opening chats: {placeholders.join(", ")}</p>}
        </div>
      )}
    </div>
  );
}
