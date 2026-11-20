import {
  Bell,
  FileText,
  GitMerge,
  Mail,
  MessageCircle,
  Pencil,
  ReceiptText,
  ScanLine,
  ShoppingBag,
  Trash2,
  UserPlus,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getCustomerActivity } from "../api/customers";
import { errorMessage } from "../api/errorMessage";
import type { ActivityItem } from "../api/types";
import ErrorText from "./ErrorText";
import Spinner from "./Spinner";

const PAGE_SIZE = 30;

const ICONS: Record<string, LucideIcon> = {
  customer_created: UserPlus,
  email: Mail,
  sms: MessageCircle,
  whatsapp: MessageCircle,
  order_created: ShoppingBag,
  order_updated: Pencil,
  order_deleted: Trash2,
  transaction_added: ReceiptText,
  transaction_updated: Pencil,
  transaction_deleted: Trash2,
  note_added: FileText,
  scan: ScanLine,
  form_submission: FileText,
  profile_updated: Pencil,
  merged: GitMerge,
  unsubscribed: Bell,
};

function formatWhen(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function dayKey(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

function tone(item: ActivityItem): string {
  if (item.status === "failed") return " activity-bad";
  if (item.status === "skipped") return " activity-muted";
  if (item.kind.endsWith("_deleted")) return " activity-bad";
  return "";
}

/** A customer's whole history in one list, newest first: messages, orders, purchases, notes,
 * edits, merges and deletions. */
export default function ActivityLog({ customerId }: { customerId: string }) {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getCustomerActivity(customerId, page, PAGE_SIZE)
      .then((res) => {
        if (cancelled) return;
        setTotal(res.total);
        // page 1 replaces (fresh open / customer switch); later pages append
        setItems((prev) => (page === 1 ? res.items : [...prev, ...res.items]));
      })
      .catch((err) => !cancelled && setError(errorMessage(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [customerId, page]);

  let lastDay = "";
  return (
    <div className="card activity-log">
      <h3 style={{ marginTop: 0 }}>Activity log</h3>
      <p className="muted small">
        Everything that has happened with this customer. WhatsApp chats show as "opened" because WhatsApp doesn't tell us whether the message was
        actually sent.
      </p>
      <ErrorText message={error} />
      {items.length === 0 && loading && <Spinner />}
      {items.length === 0 && !loading && !error && <p className="muted">Nothing recorded yet.</p>}
      <ol className="activity-list">
        {items.map((item) => {
          const Icon = ICONS[item.kind] ?? FileText;
          const day = dayKey(item.at);
          const showDay = day !== lastDay;
          lastDay = day;
          return (
            <li key={item.id}>
              {showDay && <div className="activity-day">{day}</div>}
              <div className={`activity-row${tone(item)}`}>
                <span className="activity-icon" aria-hidden="true">
                  <Icon size={15} />
                </span>
                <div className="activity-body">
                  <div className="activity-title">
                    {item.link ? <Link to={item.link}>{item.title}</Link> : item.title}
                    {item.status === "opened" && <span className="muted small"> · not confirmed sent</span>}
                  </div>
                  {item.detail && <div className="activity-detail muted small">{item.detail}</div>}
                  <div className="activity-time muted small">{formatWhen(item.at)}</div>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
      {items.length > 0 && items.length < total && (
        <button className="btn-ghost" type="button" disabled={loading} onClick={() => setPage((p) => p + 1)}>
          {loading ? "Loading…" : `Show older (${total - items.length} more)`}
        </button>
      )}
    </div>
  );
}
