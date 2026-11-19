import { api, queryString, type Paged } from "./client";
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

export function updateForm(
  id: string,
  data: Partial<FormInput> & { is_active?: boolean; regenerate_token?: boolean; enable_signing?: boolean; disable_signing?: boolean }
): Promise<CustomForm> {
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

export function submitPublicForm(token: string, data: Record<string, unknown>): Promise<{ status: string; customer_created: boolean }> {
  return api.post(`/api/public/forms/${token}/submit`, data);
}

export function listSubmissionsPaged(formId: string, params: { page: number; pageSize: number }): Promise<Paged<FormSubmission>> {
  return api.getPaged<FormSubmission>(`/api/forms/${formId}/submissions${queryString({ page: params.page, page_size: params.pageSize })}`);
}

export function listFormsPaged(params: { search?: string; page: number; pageSize: number }): Promise<Paged<CustomForm>> {
  return api.getPaged<CustomForm>(`/api/forms${queryString({ search: params.search, page: params.page, page_size: params.pageSize })}`);
}
