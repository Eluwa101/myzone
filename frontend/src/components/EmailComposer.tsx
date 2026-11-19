import { AlertTriangle, MessageCircle, Send, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { errorMessage } from "../api/errorMessage";
import { getDefaultCountryCode } from "../api/settings";
import { buildWaLink, htmlToPlainText, normalizePhone } from "../utils/whatsapp";
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
  const [countryCode, setCountryCode] = useState("");
  const [whatsappArmed, setWhatsappArmed] = useState(false);
  // customers whose chat was opened for this exact draft (cleared when it changes)
  const [whatsappOpened, setWhatsappOpened] = useState<Set<string>>(new Set());
  // only the latest preview request may write results - a slow response for an
  // earlier draft or customer must not overwrite a newer one
  const whatsappRequestRef = useRef(0);

  useEffect(() => {
    getDefaultCountryCode().then(setCountryCode);
  }, []);

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
  const withPhone = (recipients ?? []).filter((recipient) => recipient.phone);
  const whatsappRecipients = withPhone.flatMap((recipient) => {
    const result = normalizePhone(recipient.phone, countryCode);
    return result.ok ? [{ ...recipient, digits: result.digits }] : [];
  });
  const invalidPhoneCount = withPhone.length - whatsappRecipients.length;
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
    const requestId = ++whatsappRequestRef.current;
    setWhatsappIndex(index);
    setWhatsappLoading(true);
    setWhatsappError(null);
    setWhatsappArmed(false);
    try {
      const preview = await previewMessage(target.id, subject, bodyHtml);
      if (requestId === whatsappRequestRef.current) setWhatsappPreview(preview);
    } catch (err) {
      if (requestId === whatsappRequestRef.current) {
        setWhatsappPreview(null);
        setWhatsappError(errorMessage(err));
      }
    } finally {
      if (requestId === whatsappRequestRef.current) setWhatsappLoading(false);
    }
  }

  const whatsappText = whatsappPreview ? htmlToPlainText(whatsappPreview.body_html) : "";
  const whatsappLink = whatsappRecipient && whatsappText ? buildWaLink(whatsappRecipient.digits, whatsappText) : null;
  // anything that means this message isn't really ready: tags the server
  // couldn't fill, or [fill-in] placeholders still in the draft
  const whatsappWarnings = [
    ...(whatsappPreview?.problems?.length ? [`Merge tags that could not be filled: ${whatsappPreview.problems.join(", ")}`] : []),
    ...(findPlaceholders(bodyHtml).length ? [`Unfilled placeholders: ${findPlaceholders(bodyHtml).join(", ")}`] : []),
  ];

  function openWhatsapp() {
    if (whatsappLoading || !whatsappRecipient) return;
    if (!whatsappLink) {
      setWhatsappError("There is no message to send yet.");
      return;
    }
    if (whatsappLink.tooLong) {
      setWhatsappError("This message is too long for a WhatsApp chat link - shorten it and try again.");
      return;
    }
    // same two-step confirm as the email Send button: the first click only
    // arms it if the message still has holes in it
    if (whatsappWarnings.length > 0 && !whatsappArmed) {
      setWhatsappArmed(true);
      return;
    }
    setWhatsappArmed(false);
    window.open(whatsappLink.url, "_blank", "noopener,noreferrer");
    setWhatsappOpened((prev) => new Set(prev).add(whatsappRecipient.id));
  }

  // WhatsApp only uses the body, so subject edits must not refetch; typing in
  // the body is debounced so one preview call isn't fired per keystroke
  // callers often build `recipients` inline, so it's a new array on every
  // parent render - key on its content instead of its identity
  const recipientsKey = (recipients ?? []).map((r) => `${r.id}:${r.phone ?? ""}`).join(",");
  useEffect(() => {
    if (!showWhatsapp) return;
    whatsappRequestRef.current++; // invalidate anything still in flight
    setWhatsappLoading(false);
    setWhatsappPreview(null);
    setWhatsappIndex(0);
    setWhatsappOpened(new Set());
    setWhatsappArmed(false);
    if (!whatsappRecipients.length || !bodyHtml.trim()) return;
    const timer = setTimeout(() => void loadWhatsappPreview(0), 400);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showWhatsapp, bodyHtml, recipientsKey, countryCode]);

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
          <p className="muted small">
            This opens a chat in WhatsApp with the message already typed in, merge tags filled in for that customer - you
            review it and press send there. Only the message text is used (no subject, no unsubscribe footer).
          </p>
          <p className="muted small">
            {whatsappRecipients.length} of {count} customers have a usable phone number
            {invalidPhoneCount
              ? `; ${invalidPhoneCount} saved number${invalidPhoneCount === 1 ? " is" : "s are"} unusable (no country code, too short, or not a number)${countryCode ? "" : " - set a default country code in Settings to fix local-format numbers like 0801…"}`
              : ""}
            .
          </p>
          {whatsappRecipient && (
            <div className="row" style={{ alignItems: "center", flexWrap: "wrap" }}>
              <label htmlFor="whatsapp-recipient">Customer</label>
              <select id="whatsapp-recipient" value={whatsappIndex} onChange={(event) => void loadWhatsappPreview(Number(event.target.value))}>
                {whatsappRecipients.map((recipient, index) => (
                  <option key={recipient.id} value={index}>
                    {recipient.name} · +{recipient.digits}
                    {whatsappOpened.has(recipient.id) ? " · opened" : ""}
                  </option>
                ))}
              </select>
              {whatsappRecipients.length > 1 && <span className="muted small">{whatsappIndex + 1} of {whatsappRecipients.length}</span>}
              <button
                type="button"
                className={whatsappArmed ? "btn-danger" : "btn-primary"}
                onClick={openWhatsapp}
                disabled={whatsappLoading || !whatsappLink}
              >
                <MessageCircle size={15} /> {whatsappArmed ? "Open anyway?" : "Open WhatsApp"}
              </button>
              {whatsappRecipients.length > 1 && whatsappOpened.has(whatsappRecipient.id) && (
                <button
                  type="button"
                  onClick={() => {
                    const next = whatsappRecipients.findIndex((r, i) => i > whatsappIndex && !whatsappOpened.has(r.id));
                    const fallback = whatsappRecipients.findIndex((r) => !whatsappOpened.has(r.id));
                    const target = next !== -1 ? next : fallback;
                    if (target !== -1) void loadWhatsappPreview(target);
                  }}
                  disabled={whatsappRecipients.every((r) => whatsappOpened.has(r.id))}
                >
                  Next unopened
                </button>
              )}
            </div>
          )}
          {whatsappLoading && <p className="muted small">Preparing personalized message…</p>}
          {whatsappText && whatsappRecipient && (
            <pre className="small" style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{whatsappText}</pre>
          )}
          {whatsappLink?.tooLong && (
            <p className="tag-problems small">This message is too long to open as a WhatsApp chat link - shorten it.</p>
          )}
          {whatsappError && <ErrorText message={whatsappError} />}
          {whatsappWarnings.map((warning) => (
            <p key={warning} className="tag-problems small">{warning}</p>
          ))}
          {whatsappWarnings.length > 0 && <p className="muted small">Click "Open WhatsApp" twice to open the chat with these left in.</p>}
        </div>
      )}
    </div>
  );
}
