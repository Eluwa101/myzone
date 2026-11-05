import { Mic, Send, Square, SquarePen } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { askData } from "../api/agent";
import { errorMessage } from "../api/errorMessage";
import ErrorText from "../components/ErrorText";
import MarkdownMessage from "../components/MarkdownMessage";
import TopBar from "../components/TopBar";
import { useVoiceInput } from "../hooks/useVoiceInput";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const CHIPS = [
  "Who showed interest but hasn't bought yet?",
  "Who spent the most this month?",
  "Who should I follow up with this week?",
  "Which customers have pets?",
  "Who has no consent recorded?",
];

export default function AskDataPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const baseTextRef = useRef("");

  const voice = useVoiceInput((transcript) => {
    setInput((baseTextRef.current ? baseTextRef.current + " " : "") + transcript);
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    setInput("");
    setError(null);
    setMessages((m) => [...m, { role: "user", content: question }]);
    setBusy(true);
    try {
      const res = await askData(question);
      setMessages((m) => [...m, { role: "assistant", content: res.answer }]);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function onSend(e: FormEvent) {
    e.preventDefault();
    ask(input);
  }

  function onMicClick() {
    baseTextRef.current = input;
    voice.toggle();
  }

  return (
    <div className="chat-page">
      <TopBar
        title="Ask your data"
        actions={
          messages.length > 0 ? (
            <button className="btn-ghost icon-btn" onClick={() => setMessages([])} aria-label="New chat" title="New chat">
              <SquarePen size={18} />
            </button>
          ) : undefined
        }
      />
      <p className="muted small page-note">
        Read-only — looks across all your customers to answer questions, but can never change a record. Ask it to edit
        something and it'll tell you how to do that in the app instead.
      </p>

      {messages.length === 0 && (
        <div className="row page-note" style={{ flexWrap: "wrap" }}>
          {CHIPS.map((c) => (
            <button key={c} className="chip" onClick={() => ask(c)}>
              {c}
            </button>
          ))}
        </div>
      )}

      <div className="chat-transcript">
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble ${m.role}`}>
            {m.role === "assistant" ? <MarkdownMessage content={m.content} /> : m.content}
          </div>
        ))}
        {busy && <div className="chat-bubble assistant muted">Thinking…</div>}
        <div ref={bottomRef} />
      </div>

      <ErrorText message={error} />
      <form className="chat-input-row" onSubmit={onSend}>
        {voice.supported && (
          <button
            type="button"
            className={`icon-btn${voice.listening ? " btn-danger" : ""}`}
            onClick={onMicClick}
            disabled={busy}
            aria-label={voice.listening ? "Stop dictation" : "Dictate question"}
            title={voice.listening ? "Stop dictation" : "Dictate question"}
          >
            {voice.listening ? <Square size={16} /> : <Mic size={16} />}
          </button>
        )}
        <input
          aria-label="Question"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={voice.listening ? "Listening…" : "Ask anything about your customers…"}
          disabled={busy}
          autoFocus
        />
        <button className="btn-primary" type="submit" disabled={busy || !input.trim()} aria-label="Ask">
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}
