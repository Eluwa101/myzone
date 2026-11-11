import { Check, Search, Send, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getCustomer, listCustomers } from "../api/customers";
import { errorMessage } from "../api/errorMessage";
import { listEmailTemplates, previewMessage, sendEmail, type EmailTemplate } from "../api/messaging";
import { getSegmentMembers } from "../api/segments";
import type { Customer } from "../api/types";
import ErrorText from "../components/ErrorText";
import MergeTagPicker from "../components/MergeTagPicker";
import RichTextEditor, { type RichTextEditorHandle } from "../components/RichTextEditor";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";

interface Recipient {
  id: string;
  name: string;
  email: string | null;
}

export default function MessageComposePage() {
  const [searchParams] = useSearchParams();
  const customerId = searchParams.get("customer_id");
  const segmentId = searchParams.get("segment_id");

  const [recipients, setRecipients] = useState<Recipient[] | null>(null);
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [templateId, setTemplateId] = useState("");
  const [subject, setSubject] = useState("");
  const [bodyHtml, setBodyHtml] = useState("");
  const [skipWithoutConsent, setSkipWithoutConsent] = useState(true);
  const [previewFor, setPreviewFor] = useState<{ subject: string; body_html: string } | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeField, setActiveField] = useState<"subject" | "body">("body");

  const subjectRef = useRef<HTMLInputElement>(null);
  const editorRef = useRef<RichTextEditorHandle>(null);

  useEffect(() => {
    listEmailTemplates().then((loaded) => {
      setTemplates(loaded);
      const preselectId = searchParams.get("template_id");
      const preselect = preselectId && loaded.find((t) => t.id === preselectId);
      if (preselect) {
        setTemplateId(preselect.id);
        setSubject(preselect.subject);
        setBodyHtml(preselect.body_html);
      }
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (customerId) {
      getCustomer(customerId)
        .then((c: Customer) => setRecipients([{ id: c.id, name: c.name, email: c.email ?? null }]))
        .catch((err) => setError(errorMessage(err)));
    } else if (segmentId) {
      getSegmentMembers(segmentId)
        .then((r) => setRecipients(r.members.map((m) => ({ id: m.id, name: m.name, email: m.email }))))
        .catch((err) => setError(errorMessage(err)));
    } else {
      setRecipients([]);
    }
  }, [customerId, segmentId]);

  function onSelectTemplate(id: string) {
    setTemplateId(id);
    const t = templates.find((tpl) => tpl.id === id);
    if (t) {
      setSubject(t.subject);
      setBodyHtml(t.body_html);
    }
  }

  function insertTag(tag: string) {
    if (activeField === "subject" && subjectRef.current) {
      const el = subjectRef.current;
      const start = el.selectionStart ?? subject.length;
      const end = el.selectionEnd ?? subject.length;
      const next = subject.slice(0, start) + tag + subject.slice(end);
      setSubject(next);
      requestAnimationFrame(() => {
        el.focus();
        el.setSelectionRange(start + tag.length, start + tag.length);
      });
    } else {
      editorRef.current?.insertTextAtCursor(tag);
    }
  }

  async function onPreview() {
    if (!recipients || recipients.length === 0) return;
    setPreviewLoading(true);
    setError(null);
    try {
      const result = await previewMessage(recipients[0].id, subject, bodyHtml);
      setPreviewFor(result);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setPreviewLoading(false);
    }
  }

  async function onSend() {
    if (!recipients || recipients.length === 0 || !subject.trim() || !bodyHtml.trim()) return;
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
      setResult(parts.join(" "));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSending(false);
    }
  }

  const withEmail = (recipients ?? []).filter((r) => r.email).length;
  const withoutEmail = (recipients ?? []).length - withEmail;

  return (
    <div>
      <TopBar title="Compose email" backTo="/messages" />

      <div className="card">
        <h3>Recipients</h3>
        {recipients === null ? (
          <Spinner />
        ) : (
          <>
            <p className="small">
              {recipients.length} customer{recipients.length === 1 ? "" : "s"} selected
              {withoutEmail > 0 && <span className="muted"> ({withoutEmail} without an email on file)</span>}
            </p>
            {!customerId && !segmentId && (
              <RecipientPicker selected={recipients} onChange={setRecipients} />
            )}
          </>
        )}
      </div>

      <div className="card">
        <h3>Template (optional)</h3>
        <select aria-label="Choose a template" value={templateId} onChange={(e) => onSelectTemplate(e.target.value)}>
          <option value="">Start from scratch</option>
          {templates.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </div>

      <div className="card">
        <h3>Message</h3>
        <label htmlFor="compose-subject">Subject</label>
        <input
          id="compose-subject"
          ref={subjectRef}
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          onFocus={() => setActiveField("subject")}
        />
        <label>Body</label>
        <div onFocus={() => setActiveField("body")}>
          <RichTextEditor ref={editorRef} value={bodyHtml} onChange={setBodyHtml} placeholder="Write your message…" />
        </div>
        <div className="row" style={{ marginTop: 10 }}>
          <MergeTagPicker onInsert={insertTag} />
        </div>
        <label className="row" style={{ gap: 6, marginTop: 10 }}>
          <input type="checkbox" checked={skipWithoutConsent} onChange={(e) => setSkipWithoutConsent(e.target.checked)} />
          Skip customers with no recorded consent
        </label>
      </div>

      {previewFor && (
        <div className="card">
          <h3>Preview (first recipient)</h3>
          <p className="small">
            <b>{previewFor.subject}</b>
          </p>
          <div className="small" dangerouslySetInnerHTML={{ __html: previewFor.body_html }} />
        </div>
      )}

      <ErrorText message={error} />
      {result && <p className="muted small page-note">{result}</p>}

      <div className="row" style={{ margin: "12px 0 24px" }}>
        <button type="button" onClick={onPreview} disabled={previewLoading || !recipients?.length}>
          {previewLoading ? "Loading…" : "Preview"}
        </button>
        <button
          type="button"
          className="btn-primary"
          onClick={onSend}
          disabled={sending || !recipients?.length || !subject.trim() || !bodyHtml.trim()}
        >
          <Send size={15} /> {sending ? "Sending…" : "Send"}
        </button>
      </div>
    </div>
  );
}

function RecipientPicker({ selected, onChange }: { selected: Recipient[]; onChange: (r: Recipient[]) => void }) {
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const handle = setTimeout(() => {
      setLoading(true);
      listCustomers({ search, pageSize: 10 })
        .then((r) => setResults(r.items))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(handle);
  }, [search]);

  function add(c: Customer) {
    if (selected.some((r) => r.id === c.id)) return;
    onChange([...selected, { id: c.id, name: c.name, email: c.email ?? null }]);
  }

  function remove(id: string) {
    onChange(selected.filter((r) => r.id !== id));
  }

  return (
    <div>
      <div className="search-wrap">
        <Search size={16} className="search-icon" aria-hidden="true" />
        <input
          aria-label="Search customers to add"
          className="search-input"
          placeholder="Search customers to add…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      {loading && <p className="muted small">Searching…</p>}
      {!loading && results.length > 0 && (
        <div className="quick-create-results">
          {results.map((c) => (
            <button key={c.id} type="button" className="quick-create-result" onClick={() => add(c)}>
              <Check size={13} /> {c.name}
            </button>
          ))}
        </div>
      )}
      {selected.length > 0 && (
        <div className="recipient-chips">
          {selected.map((r) => (
            <span key={r.id} className="chip">
              {r.name}
              <button type="button" aria-label={`Remove ${r.name}`} onClick={() => remove(r.id)}>
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
