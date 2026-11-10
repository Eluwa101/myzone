import { ApiError } from "../api/client";
import { enqueue, type OutboxItem } from "./outbox";

export type QueueSpec = Omit<OutboxItem, "id" | "createdAt">;

export type OfflineResult<T> = { queued: false; data: T } | { queued: true; id: string };

/** Runs `fn` (a normal API call); if it fails because the network itself is
 * unreachable (not a validation error or any other server-returned
 * rejection), queues `spec` for replay instead of throwing, so the caller
 * can apply an optimistic local update and keep working. */
export async function withOfflineFallback<T>(fn: () => Promise<T>, spec: QueueSpec): Promise<OfflineResult<T>> {
  try {
    const data = await fn();
    return { queued: false, data };
  } catch (err) {
    if (err instanceof ApiError && err.status === 0) {
      const item = await enqueue(spec);
      return { queued: true, id: item.id };
    }
    throw err;
  }
}
