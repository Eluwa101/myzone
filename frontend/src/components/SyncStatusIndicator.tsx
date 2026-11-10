import { CloudOff, RefreshCw } from "lucide-react";
import { flushOutbox } from "../offline/outbox";
import { useOutboxStatus } from "../offline/useOnline";

export default function SyncStatusIndicator() {
  const { pending, online } = useOutboxStatus();

  if (pending === 0 && online) return null;

  return (
    <button
      type="button"
      className="icon-btn btn-ghost sync-status-indicator"
      onClick={() => flushOutbox()}
      title={
        !online
          ? `Offline${pending > 0 ? ` - ${pending} change${pending === 1 ? "" : "s"} waiting to sync` : ""}`
          : `${pending} change${pending === 1 ? "" : "s"} waiting to sync - tap to retry now`
      }
    >
      {!online ? <CloudOff size={18} /> : <RefreshCw size={18} />}
      {pending > 0 && <span className="sync-status-count">{pending}</span>}
    </button>
  );
}
