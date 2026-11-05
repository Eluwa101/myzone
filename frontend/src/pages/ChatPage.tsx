import { History, Image as ImageIcon, Mic, Send, Square, SquarePen, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { getThreadMessages, listPending, sendChat } from "../api/agent";
import { errorMessage } from "../api/errorMessage";
import type { PendingAction } from "../api/types";
import ChatHistoryPanel from "../components/ChatHistoryPanel";
import ErrorText from "../components/ErrorText";
import MarkdownMessage from "../components/MarkdownMessage";
import PendingActionCard from "../components/PendingActionCard";
import TopBar from "../components/TopBar";
import { useVoiceInput } from "../hooks/useVoiceInput";
import { fileToCompressedDataUrl } from "../utils/image";

interface Message {
  role: "user" | "assistant";
  content: string;
  imagePreview?: string;
}

export default function ChatPage() {
  const [threadId, setThreadId] = useState<string>(() => crypto.randomUUID());
  const [messages, setMessages] = useState<Message[]>([]);
  const [pending, setPending] = useState<PendingAction[]>([]);
  const [input, setInput] = useState("");
  const [image, setImage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const baseTextRef = useRef("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const voice = useVoiceInput((transcript) => {
    setInput((baseTextRef.current ? baseTextRef.current + " " : "") + transcript);
  });

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

  function newChat() {
    setThreadId(crypto.randomUUID());
    setMessages([]);
    setImage(null);
    setError(null);
  }

  async function openThread(id: string) {
    setHistoryOpen(false);
    setError(null);
    try {
      const history = await getThreadMessages(id);
      setThreadId(id);
      setMessages(history.map((m) => ({ role: m.role, content: m.content })));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  function onMicClick() {
    baseTextRef.current = input;
    voice.toggle();
  }

  async function onImageChosen(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    try {
      setImage(await fileToCompressedDataUrl(file));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function onSend(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if ((!text && !image) || busy) return;
    setInput("");
    const imageToSend = image;
    setImage(null);
    setError(null);
    setMessages((m) => [...m, { role: "user", content: text || "(sent an image)", imagePreview: imageToSend ?? undefined }]);
    setBusy(true);
    try {
      const res = await sendChat(text, threadId, imageToSend ?? undefined);
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
      <TopBar
        title="Assistant"
        actions={
          <>
            <button className="btn-ghost icon-btn" onClick={() => setHistoryOpen(true)} aria-label="Chat history" title="Past chats">
              <History size={18} />
            </button>
            {messages.length > 0 && (
              <button className="btn-ghost icon-btn" onClick={newChat} aria-label="New chat" title="New chat">
                <SquarePen size={18} />
              </button>
            )}
          </>
        }
      />
      <p className="muted small page-note">
        Ask it to look things up, add or update customers and transactions, or snap a photo of a note or form to read into
        a record. Deleting or merging customers always needs your confirmation below first.
      </p>

      {historyOpen && <ChatHistoryPanel onSelect={openThread} onClose={() => setHistoryOpen(false)} />}

      {pending.map((p) => (
        <PendingActionCard key={p.id} action={p} onResolved={refreshPending} />
      ))}

      <div className="chat-transcript">
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble ${m.role}`}>
            {m.imagePreview && <img src={m.imagePreview} alt="Attached" className="chat-image" />}
            {m.role === "assistant" ? <MarkdownMessage content={m.content} /> : m.content}
          </div>
        ))}
        {busy && <div className="chat-bubble assistant muted">Thinking…</div>}
        <div ref={bottomRef} />
      </div>

      <ErrorText message={error} />
      {image && (
        <div className="image-draft page-note">
          <img src={image} alt="Selected" />
          <button type="button" className="icon-btn" onClick={() => setImage(null)} aria-label="Remove image">
            <X size={14} />
          </button>
        </div>
      )}
      <form className="chat-input-row" onSubmit={onSend}>
        <input ref={fileInputRef} type="file" accept="image/*" hidden onChange={onImageChosen} />
        <button
          type="button"
          className="icon-btn"
          onClick={() => fileInputRef.current?.click()}
          disabled={busy}
          aria-label="Attach image"
          title="Attach a photo"
        >
          <ImageIcon size={16} />
        </button>
        {voice.supported && (
          <button
            type="button"
            className={`icon-btn${voice.listening ? " btn-danger" : ""}`}
            onClick={onMicClick}
            disabled={busy}
            aria-label={voice.listening ? "Stop dictation" : "Dictate message"}
            title={voice.listening ? "Stop dictation" : "Dictate message"}
          >
            {voice.listening ? <Square size={16} /> : <Mic size={16} />}
          </button>
        )}
        <input
          aria-label="Message"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={voice.listening ? "Listening…" : "Ask your assistant…"}
          disabled={busy}
          autoFocus
        />
        <button className="btn-primary" type="submit" disabled={busy || (!input.trim() && !image)} aria-label="Send message">
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}
