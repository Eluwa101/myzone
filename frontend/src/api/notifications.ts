import { api } from "./client";

export interface Notification {
  id: string;
  type: string;
  title: string;
  body?: string | null;
  link?: string | null;
  read: boolean;
  created_at: string;
}

export function listNotifications(): Promise<Notification[]> {
  return api.get<Notification[]>("/api/notifications");
}

export function getUnreadNotificationCount(): Promise<{ count: number }> {
  return api.get<{ count: number }>("/api/notifications/unread-count");
}

export function markNotificationRead(id: string): Promise<Notification> {
  return api.post<Notification>(`/api/notifications/${id}/read`);
}

export function markAllNotificationsRead(): Promise<{ updated: number }> {
  return api.post<{ updated: number }>("/api/notifications/read-all");
}
