import { CloudOff } from "lucide-react";

export default function PendingSyncBadge() {
  return (
    <span className="pending-sync-badge" title="Saved locally - will sync once you're back online">
      <CloudOff size={11} /> Pending sync
    </span>
  );
}
