import { useEffect, useRef, useState } from "react";
import { listOutbox, subscribeOutbox } from "./outbox";

/** Tracks optimistic items added to the UI while offline, keyed by their
 * outbox id, and calls `onSynced` once the matching outbox entry has been
 * replayed successfully (so the caller can drop its local copy and let the
 * now-authoritative server data take over). */
export function usePendingSync<T>(onSynced: () => void) {
  const [pending, setPending] = useState<{ id: string; data: T }[]>([]);
  const onSyncedRef = useRef(onSynced);
  onSyncedRef.current = onSynced;

  useEffect(() => {
    return subscribeOutbox(() => {
      listOutbox().then((items) => {
        const liveIds = new Set(items.map((i) => i.id));
        setPending((prev) => {
          const stillPending = prev.filter((p) => liveIds.has(p.id));
          if (stillPending.length !== prev.length) onSyncedRef.current();
          return stillPending;
        });
      });
    });
  }, []);

  function add(id: string, data: T) {
    setPending((prev) => [...prev, { id, data }]);
  }

  return { pending, add };
}
