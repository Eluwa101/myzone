import { BASE_URL, getToken } from "../api/client";

export interface OutboxItem {
  id: string;
  method: "POST" | "PATCH" | "PUT" | "DELETE";
  path: string;
  body: unknown;
  label: string;
  createdAt: number;
}

const DB_NAME = "myshop-offline";
const STORE = "outbox";

let dbPromise: Promise<IDBDatabase> | null = null;

function openDb(): Promise<IDBDatabase> {
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        req.result.createObjectStore(STORE, { keyPath: "id" });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  return dbPromise;
}

type Listener = () => void;
const listeners = new Set<Listener>();

export function subscribeOutbox(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function notify(): void {
  listeners.forEach((l) => l());
}

export async function enqueue(item: Omit<OutboxItem, "id" | "createdAt">): Promise<OutboxItem> {
  const db = await openDb();
  const full: OutboxItem = { ...item, id: crypto.randomUUID(), createdAt: Date.now() };
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).add(full);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  notify();
  return full;
}

export async function listOutbox(): Promise<OutboxItem[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, "readonly");
    const req = tx.objectStore(STORE).getAll();
    req.onsuccess = () => resolve((req.result as OutboxItem[]).sort((a, b) => a.createdAt - b.createdAt));
    req.onerror = () => reject(req.error);
  });
}

async function removeFromOutbox(id: string): Promise<void> {
  const db = await openDb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).delete(id);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  notify();
}

let flushing = false;

/** Replays queued requests in the order they were made. Stops at the first
 * one that still can't reach the server (still offline) so later items
 * never jump ahead of an earlier one that hasn't landed yet. A request that
 * reaches the server but is rejected (e.g. the record it referenced was
 * since deleted) is dropped - it can never succeed by retrying. */
export async function flushOutbox(): Promise<{ synced: number; droppedNonRetryable: number; stillOffline: boolean }> {
  if (flushing) return { synced: 0, droppedNonRetryable: 0, stillOffline: false };
  flushing = true;
  let synced = 0;
  let droppedNonRetryable = 0;
  let stillOffline = false;
  try {
    const items = await listOutbox();
    for (const item of items) {
      const token = getToken();
      let res: Response;
      try {
        res = await fetch(`${BASE_URL}${item.path}`, {
          method: item.method,
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            "Idempotency-Key": item.id,
          },
          body: item.body !== undefined ? JSON.stringify(item.body) : undefined,
        });
      } catch {
        stillOffline = true;
        break;
      }
      if (res.ok) {
        await removeFromOutbox(item.id);
        synced++;
      } else if (res.status >= 500) {
        // Transient server-side issue - leave it queued and try again later.
        stillOffline = true;
        break;
      } else {
        await removeFromOutbox(item.id);
        droppedNonRetryable++;
      }
    }
  } finally {
    flushing = false;
  }
  return { synced, droppedNonRetryable, stillOffline };
}
