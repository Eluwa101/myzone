import { api } from "./client";

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
  subject: string | null;
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
