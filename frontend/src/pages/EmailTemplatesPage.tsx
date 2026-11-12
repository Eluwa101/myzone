import { Check, Eye, EyeOff, Mail, Pencil, Plus, Send, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../api/errorMessage";
import {
  createEmailTemplate,
  deleteEmailTemplate,
  listEmailTemplates,
  updateEmailTemplate,
  type EmailTemplate,
} from "../api/messaging";
import CardHead from "../components/CardHead";
import ErrorText from "../components/ErrorText";
import MergeTagPicker from "../components/MergeTagPicker";
import EmailBodyEditor, { type EmailBodyEditorHandle } from "../components/EmailBodyEditor";
import HtmlPreviewFrame from "../components/HtmlPreviewFrame";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";

export default function EmailTemplatesPage() {
  const [templates, setTemplates] = useState<EmailTemplate[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    listEmailTemplates()
      .then(setTemplates)
      .catch((err) => setError(errorMessage(err)));
  }
  useEffect(load, []);

  return (
    <div>
      <TopBar title="Email templates" backTo="/messages" />
      <p className="muted small page-note">
        Reusable email content with merge tags - pick one from the compose screen instead of writing from scratch each time.
        Switch the body to HTML to design with tables, colours and images.
      </p>
      <ErrorText message={error} />

      {adding ? (
        <div className="card form-card">
          <TemplateEditor
            onCancel={() => setAdding(false)}
            onSaved={() => {
              setAdding(false);
              load();
            }}
          />
        </div>
      ) : (
        <div className="page-actions">
          <button type="button" className="btn-primary" onClick={() => setAdding(true)}>
            <Plus size={15} /> New template
          </button>
        </div>
      )}

      {templates === null ? (
        <Spinner />
      ) : templates.length === 0 ? (
        <div className="empty-state">
          <Mail size={40} className="empty-state-icon" strokeWidth={1.5} />
          <p>No templates yet.</p>
        </div>
      ) : (
        <div className="card-grid">
          {templates.map((t) => (
            <TemplateCard key={t.id} template={t} onChanged={load} />
          ))}
        </div>
      )}
    </div>
  );
}

function TemplateEditor({
  template,
  onCancel,
  onSaved,
}: {
  template?: EmailTemplate;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(template?.name ?? "");
  const [subject, setSubject] = useState(template?.subject ?? "");
  const [bodyHtml, setBodyHtml] = useState(template?.body_html ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const editorRef = useRef<EmailBodyEditorHandle>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || !subject.trim() || !bodyHtml.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const payload = { name: name.trim(), subject: subject.trim(), body_html: bodyHtml };
      if (template) await updateEmailTemplate(template.id, payload);
      else await createEmailTemplate(payload);
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="info-row-editing" onSubmit={onSubmit}>
      <label htmlFor="tpl-name">Template name</label>
      <input id="tpl-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Monthly promo" autoFocus />
      <label htmlFor="tpl-subject">Subject</label>
      <input id="tpl-subject" value={subject} onChange={(e) => setSubject(e.target.value)} />
      <label>Body</label>
      <EmailBodyEditor ref={editorRef} value={bodyHtml} onChange={setBodyHtml} placeholder="Write your template…" />
      <div className="row" style={{ marginTop: 10 }}>
        <MergeTagPicker onInsert={(tag) => editorRef.current?.insertTextAtCursor(tag)} />
      </div>
      <ErrorText message={error} />
      <div className="row" style={{ marginTop: 10 }}>
        <button type="submit" className="btn-primary" disabled={busy}>
          <Check size={15} /> Save
        </button>
        <button type="button" onClick={onCancel} disabled={busy}>
          <X size={15} /> Cancel
        </button>
      </div>
    </form>
  );
}

function TemplateCard({ template, onChanged }: { template: EmailTemplate; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [showDesign, setShowDesign] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    try {
      await deleteEmailTemplate(template.id);
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  if (editing) {
    return (
      <div className="card note-card span-all form-card">
        <TemplateEditor template={template} onCancel={() => setEditing(false)} onSaved={() => { setEditing(false); onChanged(); }} />
      </div>
    );
  }

  return (
    <div className="card note-card">
      <CardHead
        icon={<Mail />}
        tone="teal"
        title={template.name}
        subtitle={template.subject}
        items={[
          { key: "edit", label: "Edit", icon: <Pencil />, onSelect: () => setEditing(true) },
          {
            key: "design",
            label: showDesign ? "Hide design" : "View design",
            icon: showDesign ? <EyeOff /> : <Eye />,
            onSelect: () => setShowDesign((v) => !v),
          },
          { key: "div", divider: true },
          { key: "delete", label: "Delete template", icon: <Trash2 />, danger: true, confirm: "Really delete?", onSelect: remove },
        ]}
      />
      {showDesign && <HtmlPreviewFrame html={template.body_html} title={`${template.name} design`} />}
      <ErrorText message={error} />
      <div className="card-actions">
        <Link to={`/messages/compose?template_id=${template.id}`} className="btn-primary">
          <Send size={13} /> Use this template
        </Link>
      </div>
    </div>
  );
}
