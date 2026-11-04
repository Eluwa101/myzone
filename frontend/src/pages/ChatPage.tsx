import { useEffect, useRef, useState, type FormEvent } from "react";
import { listPending, sendChat } from "../api/agent";
import { errorMessage } from "../api/errorMessage";
import type { PendingAction } from "../api/types";
import ErrorText from "../components/ErrorText";
import PendingActionCard from "../components/PendingActionCard";
import TopBar from "../components/TopBar";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [pending, setPending] = useState<PendingAction[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  function refreshPending() {
    listPending()
      .then(setPending)
      .catch(() => {
        /* non-fatal - chat still works without this */
      });
  }

  useEffect(refreshPending, []);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

  async function onSend(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setError(null);
    setMessages((m) => [...m, { role: "user", content: text }]);
    setBusy(true);
    try {
      const res = await sendChat(text);
      setMessages((m) => [...m, { role: "assistant", content: res.reply }]);
      if (res.pending_actions.length) refreshPending();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="chat-page">
      <TopBar title="Assistant" />
      <p className="muted small">
        Ask it to look things up, add or update customers and transactions. Deleting or merging customers always needs your
        confirmation below first.
      </p>

      {pending.map((p) => (
        <PendingActionCard key={p.id} action={p} onResolved={refreshPending} />
      ))}

      <div className="chat-transcript">
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble ${m.role}`}>
            {m.content}
          </div>
        ))}
        {busy && <div className="chat-bubble assistant muted">Thinking…</div>}
        <div ref={bottomRef} />
      </div>

      <ErrorText message={error} />
      <form className="chat-input-row" onSubmit={onSend}>
        <input
          aria-label="Message"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask your assistant…"
          disabled={busy}
          autoFocus
        />
        <button className="btn-primary" type="submit" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
