import { useEffect, useState } from "react";
import { flushOutbox, listOutbox, subscribeOutbox } from "./outbox";

const RETRY_INTERVAL_MS = 30_000;

let flushScheduled = false;

function scheduleFlush() {
  if (flushScheduled) return;
  flushScheduled = true;
  // Debounce bursts of "online" signals (browser event + periodic timer
  // landing close together) into a single flush pass.
  setTimeout(() => {
    flushScheduled = false;
    flushOutbox();
  }, 300);
}

if (typeof window !== "undefined") {
  window.addEventListener("online", scheduleFlush);
  setInterval(() => {
    if (navigator.onLine) scheduleFlush();
  }, RETRY_INTERVAL_MS);
}

/** Queued-item count plus online status, for the header sync indicator.
 * Also the trigger point that keeps retrying the outbox while the tab is
 * open, so a reconnect gets picked up even without the `online` event
 * firing reliably (some browsers don't fire it on flaky connections). */
export function useOutboxStatus() {
  const [pending, setPending] = useState(0);
  const [online, setOnline] = useState(() => (typeof navigator === "undefined" ? true : navigator.onLine));

  useEffect(() => {
    let cancelled = false;
    function refresh() {
      listOutbox().then((items) => {
        if (!cancelled) setPending(items.length);
      });
    }
    refresh();
    const unsubscribe = subscribeOutbox(refresh);

    function onOnline() {
      setOnline(true);
      scheduleFlush();
    }
    function onOffline() {
      setOnline(false);
    }
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);

    return () => {
      cancelled = true;
      unsubscribe();
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  return { pending, online };
}
