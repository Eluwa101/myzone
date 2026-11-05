import { Loader2 } from "lucide-react";
import { useServerWaking } from "../hooks/useServerWaking";

export default function ServerWakingBanner() {
  const waking = useServerWaking();
  if (!waking) return null;

  return (
    <div className="server-waking-banner" role="status">
      <Loader2 size={14} className="spin" />
      Waking up the server, this can take up to a minute…
    </div>
  );
}
