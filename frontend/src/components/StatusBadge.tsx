import type { CustomerStatus } from "../api/types";

export default function StatusBadge({ status }: { status: CustomerStatus }) {
  return <span className={`badge badge-${status}`}>{status}</span>;
}
