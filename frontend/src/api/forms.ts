import { api } from "./client";
import type { CustomForm, FormFieldDef, FormSubmission, PublicForm } from "./types";

export interface FormInput {
  name: string;
  fields: FormFieldDef[];
}

export function listForms(): Promise<CustomForm[]> {
  return api.get<CustomForm[]>("/api/forms");
}

export function createForm(data: FormInput): Promise<CustomForm> {
  return api.post<CustomForm>("/api/forms", data);
}

export function getForm(id: string): Promise<CustomForm> {
  return api.get<CustomForm>(`/api/forms/${id}`);
}

export function updateForm(id: string, data: Partial<FormInput> & { is_active?: boolean; regenerate_token?: boolean }): Promise<CustomForm> {
  return api.patch<CustomForm>(`/api/forms/${id}`, data);
}

export function deleteForm(id: string): Promise<void> {
  return api.delete<void>(`/api/forms/${id}`);
}

export function listSubmissions(formId: string): Promise<FormSubmission[]> {
  return api.get<FormSubmission[]>(`/api/forms/${formId}/submissions`);
}

export function getPublicForm(token: string): Promise<PublicForm> {
  return api.get<PublicForm>(`/api/public/forms/${token}`);
}

export function submitPublicForm(token: string, data: Record<string, string>): Promise<{ status: string; customer_created: boolean }> {
  return api.post(`/api/public/forms/${token}/submit`, data);
}
