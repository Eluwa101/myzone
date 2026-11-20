import { Sparkles } from "lucide-react";
import { useId, useState, type ReactNode } from "react";
import { errorMessage } from "../api/errorMessage";
import ErrorText from "./ErrorText";

/** "Describe it and the assistant writes it" - the same card for an email and for a WhatsApp
 * message. It owns the prompt box and the busy / error state; the caller supplies what to do
 * with the description (return true when it worked, and the box clears). Once there is text to
 * work from, it becomes "describe a change" instead. */
export default function AssistantCard({
  hasContent,
  noun,
  placeholderNew,
  placeholderChange,
  onSubmit,
  children,
}: {
  /** there is already a message, so the description is a change to it */
  hasContent: boolean;
  /** "email" | "message" - used in the label and the button */
  noun: string;
  placeholderNew: string;
  placeholderChange: string;
  /** write or change the message; resolve true on success so the box can clear */
  onSubmit: (description: string) => Promise<boolean>;
  /** extra controls beside the button, e.g. the email style picker */
  children?: ReactNode;
}) {
  const id = useId();
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!prompt.trim()) return;
    setBusy(true);
    setError(null);
    try {
      if (await onSubmit(prompt.trim())) setPrompt("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card assistant-suggest-card">
      <label htmlFor={id}>
        <Sparkles size={13} className="h3-icon" />{" "}
        {hasContent ? `Describe a change, and the assistant will rewrite the ${noun}` : `Describe the ${noun}, and the assistant will write it`}
      </label>
      <textarea
        id={id}
        rows={2}
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder={hasContent ? placeholderChange : placeholderNew}
      />
      <div className="row" style={{ alignItems: "center" }}>
        {children}
        <button type="button" onClick={submit} disabled={busy || !prompt.trim()}>
          <Sparkles size={14} /> {busy ? "Writing…" : hasContent ? "Rewrite" : `Write ${noun}`}
        </button>
      </div>
      <ErrorText message={error} />
    </div>
  );
}
