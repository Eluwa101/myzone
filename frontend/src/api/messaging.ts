import { api, queryString, type Paged } from "./client";

export interface MergeTag {
  category: string;
  category_label: string;
  key: string;
  label: string;
  tag: string;
}

export interface EmailTemplate {
  id: string;
  name: string;
  subject: string;
  body_html: string;
  created_at: string;
  updated_at: string;
}

export interface EmailTemplateInput {
  name: string;
  subject: string;
  body_html: string;
}

export interface SendEmailInput {
  customer_ids: string[];
  subject: string;
  body_html: string;
  template_id?: string | null;
  skip_without_consent?: boolean;
}

export interface SendEmailResult {
  queued: number;
  skipped_no_email: number;
  skipped_no_consent: number;
  skipped_unsubscribed?: number;
}

export interface OutboundMessage {
  id: string;
  customer_id: string;
  channel: string;
  status: string;
  customer_name: string | null;
  subject: string | null;
  /** first ~160 characters, tags stripped - safe to show in a list */
  body_preview: string;
  /** the full stored message; only returned by the single-message endpoint */
  body?: string | null;
  error: string | null;
  created_at: string;
}

export function listMergeTags(): Promise<MergeTag[]> {
  return api.get<MergeTag[]>("/api/messages/merge-tags");
}

export function listEmailTemplates(): Promise<EmailTemplate[]> {
  return api.get<EmailTemplate[]>("/api/messages/templates");
}

export function createEmailTemplate(data: EmailTemplateInput): Promise<EmailTemplate> {
  return api.post<EmailTemplate>("/api/messages/templates", data);
}

export function updateEmailTemplate(id: string, data: Partial<EmailTemplateInput>): Promise<EmailTemplate> {
  return api.patch<EmailTemplate>(`/api/messages/templates/${id}`, data);
}

export function deleteEmailTemplate(id: string): Promise<void> {
  return api.delete<void>(`/api/messages/templates/${id}`);
}

export interface MessagePreview {
  subject: string;
  body_html: string;
  /** merge tags that won't resolve - typos, unknown fields, unclosed blocks */
  problems?: string[];
}

export function previewMessage(customerId: string, subject: string, bodyHtml: string): Promise<MessagePreview> {
  return api.post<MessagePreview>("/api/messages/preview", {
    customer_id: customerId,
    subject,
    body_html: bodyHtml,
  });
}

export interface WhatsappDraft {
  text: string;
  problems: string[];
  placeholders: string[];
}

/** The assistant writes (or, with currentText, rewrites) a WhatsApp message from a description. */
export function draftWhatsapp(data: { description: string; segmentId?: string | null; currentText?: string | null }): Promise<WhatsappDraft> {
  return api.post<WhatsappDraft>("/api/messages/draft-whatsapp", {
    description: data.description,
    segment_id: data.segmentId ?? null,
    current_text: data.currentText ?? null,
  });
}

export type RewriteAction = "shorten" | "reformat" | "friendlier" | "rewrite";

export interface RewriteResult {
  subject: string | null;
  body: string;
  /** the original came back because no safe rewrite was possible */
  unchanged: boolean;
  warning: string | null;
  placeholders: string[];
}

/** Shorten / reformat / soften / rewrite a message that is already written. With keepMergeTags on
 * the server guarantees every merge tag comes back exactly as written. */
export function rewriteMessage(data: {
  channel: "email" | "whatsapp";
  action: RewriteAction;
  body: string;
  subject?: string | null;
  instruction?: string;
  keepMergeTags: boolean;
}): Promise<RewriteResult> {
  return api.post<RewriteResult>("/api/messages/rewrite", {
    channel: data.channel,
    action: data.action,
    body: data.body,
    subject: data.subject ?? null,
    instruction: data.instruction ?? null,
    keep_merge_tags: data.keepMergeTags,
  });
}

export interface MessagePreviewBatch {
  previews: { customer_id: string; subject: string; body_html: string }[];
  /** about the draft, not any one recipient - reported once */
  problems: string[];
  placeholders: string[];
  /** ids that no longer exist - skipped */
  missing: string[];
}

/** The same merge-tag resolution as previewMessage, for up to 50 customers in one call. */
export function previewMessageBatch(customerIds: string[], subject: string, bodyHtml: string): Promise<MessagePreviewBatch> {
  return api.post<MessagePreviewBatch>("/api/messages/preview-batch", {
    customer_ids: customerIds,
    subject,
    body_html: bodyHtml,
  });
}

export function sendEmail(data: SendEmailInput): Promise<SendEmailResult> {
  return api.post<SendEmailResult>("/api/messages/send", data);
}

export function listMessageHistory(customerId?: string): Promise<OutboundMessage[]> {
  const qs = customerId ? `?customer_id=${customerId}` : "";
  return api.get<OutboundMessage[]>(`/api/messages/history${qs}`);
}

export interface SuggestedMergeTag {
  label: string;
  tag: string;
  reason: string;
}

export function listSuggestedMergeTags(segmentId: string): Promise<SuggestedMergeTag[]> {
  return api.get<SuggestedMergeTag[]>(`/api/messages/merge-tags/suggested?segment_id=${segmentId}`);
}

export interface EmailDraftInput {
  description: string;
  segment_id?: string | null;
  format: "simple" | "designed";
  current_subject?: string | null;
  current_body?: string | null;
}

export function draftEmail(data: EmailDraftInput): Promise<MessagePreview> {
  return api.post<MessagePreview>("/api/messages/draft", data);
}

export function listEmailTemplatesPaged(params: { search?: string; page: number; pageSize: number }): Promise<Paged<EmailTemplate>> {
  return api.getPaged<EmailTemplate>(`/api/messages/templates${queryString({ search: params.search, page: params.page, page_size: params.pageSize })}`);
}

export function listMessageHistoryPaged(params: {
  customerId?: string;
  channel?: string;
  status?: string;
  search?: string;
  page: number;
  pageSize: number;
}): Promise<Paged<OutboundMessage>> {
  return api.getPaged<OutboundMessage>(
    `/api/messages/history${queryString({
      customer_id: params.customerId,
      channel: params.channel,
      status: params.status,
      search: params.search,
      page: params.page,
      page_size: params.pageSize,
    })}`
  );
}

export function getMessage(id: string): Promise<OutboundMessage> {
  return api.get<OutboundMessage>(`/api/messages/history/${id}`);
}
