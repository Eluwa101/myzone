import { Bot, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { errorMessage } from "../api/errorMessage";
import { getSqlSchema, suggestSegmentSql, type SandboxTable } from "../api/segments";
import ErrorText from "./ErrorText";

const EXAMPLES: { label: string; sql: string }[] = [
  {
    label: "Bought an item 3+ times in 90 days",
    sql: `SELECT c.id
FROM customers c
JOIN transaction_items ti ON ti.customer_id = c.id
WHERE LOWER(ti.item) LIKE '%lighter%'
  AND ti.date >= date('now', '-90 days')
GROUP BY c.id
HAVING COUNT(*) >= 3`,
  },
  {
    label: "Bought X but never Y",
    sql: `SELECT c.id
FROM customers c
WHERE c.id IN (SELECT customer_id FROM transaction_items WHERE LOWER(item) LIKE '%lighter%')
  AND c.id NOT IN (SELECT customer_id FROM transaction_items WHERE LOWER(item) LIKE '%gas%')`,
  },
  {
    label: "Spent over 50,000 in total",
    sql: `SELECT c.id
FROM customers c
JOIN transactions t ON t.customer_id = c.id
GROUP BY c.id
HAVING SUM(t.amount) > 50000`,
  },
  {
    label: "Unpaid order older than 14 days",
    sql: `SELECT DISTINCT customer_id AS id
FROM orders
WHERE paid = 0 AND order_date <= date('now', '-14 days')`,
  },
];

/** The SQL half of the segment builder. Queries run on a throwaway copy of
 * this business's own data (see backend segment_sql.py), so the editor can
 * be fully free-form - the assistant writes or edits the query, the user
 * can tweak it, and the parent shows the live preview. */
export default function SqlSegmentEditor({ sql, onChange }: { sql: string; onChange: (sql: string) => void }) {
  const [schema, setSchema] = useState<SandboxTable[] | null>(null);
  const [description, setDescription] = useState("");
  const [suggesting, setSuggesting] = useState(false);
  const [suggestError, setSuggestError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    getSqlSchema()
      .then(setSchema)
      .catch(() => setSchema([]));
  }, []);

  async function onSuggest() {
    if (!description.trim()) return;
    setSuggesting(true);
    setSuggestError(null);
    try {
      const res = await suggestSegmentSql(description.trim(), sql.trim() || null);
      onChange(res.sql);
      setDescription("");
    } catch (err) {
      setSuggestError(errorMessage(err));
    } finally {
      setSuggesting(false);
    }
  }

  function insertColumn(text: string) {
    const el = textareaRef.current;
    const start = el?.selectionStart ?? sql.length;
    const end = el?.selectionEnd ?? sql.length;
    onChange(sql.slice(0, start) + text + sql.slice(end));
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(start + text.length, start + text.length);
    });
  }

  const editing = sql.trim().length > 0;

  return (
    <div>
      <div className="card assistant-suggest-card">
        <label htmlFor="seg-sql-describe">
          <Bot size={13} className="h3-icon" /> {editing ? "Describe a change, and the assistant will update the query" : "Describe who you want, and the assistant will write the query"}
        </label>
        <div className="row">
          <input
            id="seg-sql-describe"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                onSuggest();
              }
            }}
            placeholder={editing ? "e.g. only people who also have an email" : "e.g. bought a lighter 3+ times in 90 days but never bought gas"}
            style={{ flex: 1 }}
          />
          <button type="button" onClick={onSuggest} disabled={suggesting || !description.trim()}>
            <Sparkles size={14} /> {suggesting ? "Writing…" : editing ? "Update SQL" : "Write SQL"}
          </button>
        </div>
        <ErrorText message={suggestError} />
      </div>

      <label htmlFor="seg-sql">SQL</label>
      <textarea
        id="seg-sql"
        ref={textareaRef}
        className="html-source"
        rows={9}
        spellCheck={false}
        value={sql}
        onChange={(e) => onChange(e.target.value)}
        placeholder={"SELECT c.id\nFROM customers c\nWHERE …"}
      />
      <p className="muted small" style={{ marginTop: 4 }}>
        Return the customer <code>id</code>. Runs on a private, read-only copy of your own data (SQLite). Dates are{" "}
        <code>'YYYY-MM-DD'</code>, e.g. <code>date('now', '-30 days')</code>; yes/no columns are <code>1</code>/<code>0</code>.
      </p>

      <details className="sql-reference">
        <summary className="small">Examples</summary>
        <div className="sql-examples">
          {EXAMPLES.map((ex) => (
            <button key={ex.label} type="button" className="chip" onClick={() => onChange(ex.sql)}>
              {ex.label}
            </button>
          ))}
        </div>
      </details>

      <details className="sql-reference">
        <summary className="small">Tables you can use</summary>
        {schema === null ? (
          <p className="muted small">Loading…</p>
        ) : (
          schema.map((t) => (
            <div key={t.name} className="sql-table">
              <button type="button" className="sql-table-name" onClick={() => insertColumn(t.name)}>
                {t.name}
              </button>
              <div className="sql-columns">
                {t.columns.map((c) => (
                  <button
                    key={c.name}
                    type="button"
                    className="sql-column"
                    title={[c.type, c.description].filter(Boolean).join(" - ")}
                    onClick={() => insertColumn(c.name)}
                  >
                    {c.name}
                  </button>
                ))}
              </div>
            </div>
          ))
        )}
        <p className="muted small">Click a name to insert it at the cursor. Hover a column for details.</p>
      </details>
    </div>
  );
}
