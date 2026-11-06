import { Bookmark, BookmarkCheck, Mic, Send, Square, SquarePen } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { askData } from "../api/agent";
import { errorMessage } from "../api/errorMessage";
import { createWidget } from "../api/widgets";
import ErrorText from "../components/ErrorText";
import MarkdownMessage from "../components/MarkdownMessage";
import TopBar from "../components/TopBar";
import { useVoiceInput } from "../hooks/useVoiceInput";

interface Message {
  role: "user" | "assistant";
  content: string;
  question?: string;
  saved?: boolean;
}

const CHIPS = [
  "Who showed interest but hasn't bought yet?",
  "Who spent the most this month?",
  "Who should I follow up with this week?",
  "Which customers have pets?",
  "Who has no consent recorded?",
];

const AUTO_SEND_SECONDS = 3;

export default function AskDataPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoSendCountdown, setAutoSendCountdown] = useState<number | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const baseTextRef = useRef("");
  const inputRef = useRef(input);
  const autoSendIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    inputRef.current = input;
  }, [input]);

  useEffect(() => {
    return () => {
      if (autoSendIntervalRef.current) clearInterval(autoSendIntervalRef.current);
    };
  }, []);

  function cancelAutoSend() {
    if (autoSendIntervalRef.current) {
      clearInterval(autoSendIntervalRef.current);
      autoSendIntervalRef.current = null;
    }
    setAutoSendCountdown(null);
  }

  function scheduleAutoSend() {
    setAutoSendCountdown(AUTO_SEND_SECONDS);
    autoSendIntervalRef.current = setInterval(() => {
      setAutoSendCountdown((n) => {
        if (n === null || n <= 1) {
          if (autoSendIntervalRef.current) clearInterval(autoSendIntervalRef.current);
          autoSendIntervalRef.current = null;
          ask(inputRef.current);
          return null;
        }
        return n - 1;
      });
    }, 1000);
  }

  const voice = useVoiceInput(
    (transcript) => {
      setInput((baseTextRef.current ? baseTextRef.current + " " : "") + transcript);
    },
    () => {
      if (inputRef.current.trim()) scheduleAutoSend();
    }
  );

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
      setMessages((m) => [...m, { role: "assistant", content: res.answer, question }]);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function onSend(e: FormEvent) {
    e.preventDefault();
    cancelAutoSend();
    ask(input);
  }

  function onMicClick() {
    cancelAutoSend();
    baseTextRef.current = input;
    voice.toggle();
  }

  async function saveToDashboard(index: number) {
    const msg = messages[index];
    if (!msg.question) return;
    try {
      await createWidget(msg.question);
      setMessages((m) => m.map((mm, i) => (i === index ? { ...mm, saved: true } : mm)));
    } catch (err) {
      setError(errorMessage(err));
    }
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
            {m.role === "assistant" && m.question && (
              <button
                type="button"
                className={`btn-ghost small${m.saved ? "" : " icon-btn"}`}
                style={{ marginTop: 8, padding: "4px 8px" }}
                onClick={() => saveToDashboard(i)}
                disabled={m.saved}
              >
                {m.saved ? (
                  <>
                    <BookmarkCheck size={13} /> Saved
                  </>
                ) : (
                  <>
                    <Bookmark size={13} /> Save to Dashboard
                  </>
                )}
              </button>
            )}
          </div>
        ))}
        {busy && <div className="chat-bubble assistant muted">Thinking…</div>}
        <div ref={bottomRef} />
      </div>

      <ErrorText message={error} />
      {autoSendCountdown !== null && (
        <div className="auto-send-banner row-between">
          <span>Sending in {autoSendCountdown}s…</span>
          <div className="row" style={{ gap: 8 }}>
            <button type="button" className="btn-ghost small" onClick={cancelAutoSend}>
              Cancel
            </button>
            <button
              type="button"
              className="btn-primary small"
              onClick={() => {
                cancelAutoSend();
                ask(input);
              }}
            >
              Send now
            </button>
          </div>
        </div>
      )}
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
          onChange={(e) => {
            setInput(e.target.value);
            cancelAutoSend();
          }}
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
