import { useEffect, useMemo, useState } from "react";
import { getDefaultCountryCode } from "../api/settings";
import { listEmailTemplates, listSuggestedMergeTags, type EmailTemplate, type SuggestedMergeTag } from "../api/messaging";
import { looksLikeCustomHtml } from "../utils/composer";
import { normalizePhone } from "../utils/whatsapp";

export interface Recipient {
  id: string;
  name: string;
  email: string | null;
  phone?: string | null;
}

export interface WhatsappRecipient extends Recipient {
  /** the digits wa.me needs, from the saved phone number */
  digits: string;
}

/** The ONE draft behind every place a message is written - the compose page, a
 * customer's slide-over, a segment's Email and WhatsApp tabs. Email and WhatsApp
 * are two views of it:
 *
 *  - `subject` / `bodyHtml` are the email.
 *  - `whatsappText` is `null` while WhatsApp simply follows the email's wording,
 *    and holds the person's own text once they edit it there (merge tags and all).
 *    `resetWhatsapp()` goes back to following the email.
 *
 * Whoever owns the recipient list passes it in; this hook never decides who. */
export function useComposer({
  recipients,
  segmentId,
  initialTemplateId,
}: {
  recipients: Recipient[] | null;
  /** suggests tags that fit the segment, and tells the assistant who it's writing to */
  segmentId?: string | null;
  initialTemplateId?: string | null;
}) {
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [templateId, setTemplateId] = useState("");
  const [subject, setSubject] = useState("");
  const [bodyHtml, setBodyHtml] = useState("");
  const [whatsappText, setWhatsappText] = useState<string | null>(null);
  const [skipWithoutConsent, setSkipWithoutConsent] = useState(true);
  const [suggestions, setSuggestions] = useState<SuggestedMergeTag[]>([]);
  // bumped when the body is replaced from outside the editor (template, assistant),
  // so the editor reopens in the right mode - a designed HTML email opens in HTML
  const [editorVersion, setEditorVersion] = useState(0);
  const [draftFormat, setDraftFormat] = useState<"simple" | "designed">("simple");
  const [countryCode, setCountryCode] = useState("");
  // customers whose WhatsApp chat was opened for the current wording - kept here, not in
  // the WhatsApp tab, so switching tabs doesn't lose your place in a long list
  const [whatsappOpened, setWhatsappOpened] = useState<Set<string>>(new Set());

  useEffect(() => {
    getDefaultCountryCode().then(setCountryCode);
  }, []);

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

  function selectTemplate(id: string) {
    setTemplateId(id);
    const t = templates.find((tpl) => tpl.id === id);
    if (t) {
      setSubject(t.subject);
      setBodyHtml(t.body_html);
      setDraftFormat(looksLikeCustomHtml(t.body_html) ? "designed" : "simple");
    }
  }

  // callers often build `recipients` inline, so it's a new array on every parent
  // render - key everything derived from it on its content instead of its identity
  const recipientsKey = (recipients ?? []).map((r) => `${r.id}:${r.phone ?? ""}`).join(",");
  const whatsappRecipients = useMemo<WhatsappRecipient[]>(
    () =>
      (recipients ?? []).flatMap((r) => {
        if (!r.phone) return [];
        const result = normalizePhone(r.phone, countryCode);
        return result.ok ? [{ ...r, digits: result.digits }] : [];
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [recipientsKey, countryCode]
  );
  const withPhoneCount = (recipients ?? []).filter((r) => r.phone).length;

  return {
    recipients,
    recipientsKey,
    segmentId: segmentId ?? null,
    templates,
    templateId,
    selectTemplate,
    subject,
    setSubject,
    bodyHtml,
    setBodyHtml,
    whatsappText,
    setWhatsappText,
    resetWhatsapp: () => setWhatsappText(null),
    skipWithoutConsent,
    setSkipWithoutConsent,
    suggestions,
    editorVersion,
    bumpEditor: () => setEditorVersion((v) => v + 1),
    draftFormat,
    setDraftFormat,
    countryCode,
    whatsappRecipients,
    unusablePhoneCount: withPhoneCount - whatsappRecipients.length,
    whatsappOpened,
    setWhatsappOpened,
  };
}

export type ComposerState = ReturnType<typeof useComposer>;
