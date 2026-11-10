import { Send } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { getPublicForm, submitPublicForm } from "../api/forms";
import type { PublicForm } from "../api/types";

export default function PublicFormPage() {
  const { token } = useParams<{ token: string }>();
  const [form, setForm] = useState<PublicForm | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    getPublicForm(token)
      .then(setForm)
      .catch(() => setNotFound(true));
  }, [token]);

  function set(key: string, value: string) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitPublicForm(token, values);
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : "Something went wrong - please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="public-form-page">
      <div className="card public-form-card">
        {notFound ? (
          <p>This form isn't available anymore.</p>
        ) : !form ? (
          <p className="muted small">Loading…</p>
        ) : submitted ? (
          <>
            <h1 style={{ fontSize: 19 }}>Thank you!</h1>
            <p className="muted small">Your information has been received.</p>
          </>
        ) : (
          <form onSubmit={onSubmit}>
            {form.business_name && <p className="muted small public-form-business">{form.business_name}</p>}
            <h1 style={{ fontSize: 19 }}>{form.name}</h1>
            {form.fields.map((f) => (
              <div key={f.key}>
                <label htmlFor={`pf-${f.key}`}>
                  {f.label}
                  {f.required ? " *" : ""}
                </label>
                {f.type === "textarea" ? (
                  <textarea
                    id={`pf-${f.key}`}
                    rows={3}
                    required={f.required}
                    value={values[f.key] ?? ""}
                    onChange={(e) => set(f.key, e.target.value)}
                  />
                ) : (
                  <input
                    id={`pf-${f.key}`}
                    type={f.type}
                    required={f.required}
                    value={values[f.key] ?? ""}
                    onChange={(e) => set(f.key, e.target.value)}
                  />
                )}
              </div>
            ))}
            {error && <p className="error-text small">{error}</p>}
            <button className="btn-primary" type="submit" disabled={submitting} style={{ marginTop: 12 }}>
              <Send size={15} /> {submitting ? "Sending…" : "Submit"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
