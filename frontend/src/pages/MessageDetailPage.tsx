import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { errorMessage } from "../api/errorMessage";
import { getMessage, type OutboundMessage } from "../api/messaging";
import ErrorText from "../components/ErrorText";
import HtmlPreviewFrame from "../components/HtmlPreviewFrame";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";

const STATUS_LABEL: Record<string, string> = { sent: "Sent", failed: "Failed", skipped: "Skipped" };
const CHANNEL_LABEL: Record<string, string> = { email: "Email", whatsapp: "WhatsApp", sms: "SMS" };

/** One sent message in full - what the "Recent activity" list clips to a preview. */
export default function MessageDetailPage() {
  const { id = "" } = useParams();
  const [message, setMessage] = useState<OutboundMessage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMessage(id)
      .then(setMessage)
      .catch((err) => setError(errorMessage(err)));
  }, [id]);

  return (
    <div>
      <TopBar title="Message" backTo="/messages" />
      <ErrorText message={error} />
      {!message ? (
        error ? null : <Spinner />
      ) : (
        <div className="card">
          <h2 style={{ marginTop: 0, overflowWrap: "anywhere" }}>{message.subject || "(no subject)"}</h2>
          <p className="muted small">
            {CHANNEL_LABEL[message.channel] ?? message.channel} · {STATUS_LABEL[message.status] ?? message.status} ·{" "}
            {new Date(message.created_at).toLocaleString()}
            {message.error ? ` · ${message.error}` : ""}
          </p>
          <p className="small">
            To:{" "}
            <Link to={`/customers/${message.customer_id}`}>{message.customer_name ?? "customer"}</Link>
          </p>
          {message.body ? (
            message.channel === "email" ? (
              <HtmlPreviewFrame html={message.body} title="Sent message" />
            ) : (
              <pre className="small" style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{message.body}</pre>
            )
          ) : (
            <p className="muted small">No message body was stored.</p>
          )}
        </div>
      )}
    </div>
  );
}
