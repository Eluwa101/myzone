import { Bot, Check, Code2, ListFilter, Sparkles, X } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { createSegment, getSegmentFields, previewSegment, previewSqlSegment, suggestSegmentFilters, updateSegment } from "../api/segments";
import { errorMessage } from "../api/errorMessage";
import type { Segment, SegmentFieldsCatalog, SegmentFilters, SegmentNode, SegmentResult } from "../api/types";
import ErrorText from "./ErrorText";
import SegmentQueryBuilder, { emptyGroup, OPERATOR_LABELS } from "./SegmentQueryBuilder";
import SqlSegmentEditor from "./SqlSegmentEditor";
import Spinner from "./Spinner";

function describeNode(node: SegmentNode): string {
  if (node.type === "condition") {
    const fieldLabel = node.field.startsWith("extra.") ? node.field.slice(6) : node.field.replace(/_/g, " ");
    const opLabel = OPERATOR_LABELS[node.operator] ?? node.operator;
    if (node.operator === "is_set" || node.operator === "is_not_set") return `${fieldLabel} ${opLabel}`;
    if (node.operator === "between") return `${fieldLabel} ${opLabel} ${node.value} and ${node.value2}`;
    if (node.operator === "in_list" || node.operator === "not_in_list") return `${fieldLabel} ${opLabel} [${(node.values ?? []).join(", ")}]`;
    return `${fieldLabel} ${opLabel} "${node.value}"`;
  }
  if (node.conditions.length === 0) return "everyone";
  const joiner = node.combinator === "and" ? " and " : node.combinator === "or" ? " or " : " nor ";
  return node.conditions.map((c) => (c.type === "group" ? `(${describeNode(c)})` : describeNode(c))).join(joiner);
}

export function describeFilters(f: SegmentFilters): string {
  return f.conditions.length === 0 ? "Everyone" : describeNode(f);
}

export default function SegmentBuilder({
  initial,
  onCancel,
  onSaved,
}: {
  initial?: Segment;
  onCancel: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [filters, setFilters] = useState<SegmentFilters>(initial?.filters ?? emptyGroup());
  const [catalog, setCatalog] = useState<SegmentFieldsCatalog | null>(null);
  const [preview, setPreview] = useState<SegmentResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [description, setDescription] = useState("");
  const [suggesting, setSuggesting] = useState(false);
  const [suggestError, setSuggestError] = useState<string | null>(null);
  const [appliedSummary, setAppliedSummary] = useState<string | null>(null);
  const [mode, setMode] = useState<"builder" | "sql">(initial?.sql ? "sql" : "builder");
  const [sql, setSql] = useState(initial?.sql ?? "");
  const [sqlError, setSqlError] = useState<string | null>(null);

  useEffect(() => {
    getSegmentFields()
      .then(setCatalog)
      .catch((err) => setError(errorMessage(err)));
  }, []);

  async function onSuggest() {
    if (!description.trim()) return;
    setSuggesting(true);
    setSuggestError(null);
    setAppliedSummary(null);
    try {
      const suggested = await suggestSegmentFilters(description.trim());
      setFilters(suggested);
      setAppliedSummary(describeFilters(suggested));
    } catch (err) {
      setSuggestError(errorMessage(err));
    } finally {
      setSuggesting(false);
    }
  }

  useEffect(() => {
    if (mode !== "builder") return;
    const handle = setTimeout(() => {
      previewSegment(filters)
        .then(setPreview)
        .catch(() => setPreview(null));
    }, 300);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(filters), mode]);

  useEffect(() => {
    if (mode !== "sql") return;
    setPreview(null);
    setSqlError(null);
    if (!sql.trim()) return;
    let cancelled = false;
    const handle = setTimeout(() => {
      previewSqlSegment(sql)
        .then((r) => !cancelled && setPreview(r))
        .catch((err) => !cancelled && setSqlError(errorMessage(err)));
    }, 600);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [sql, mode]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    if (mode === "sql" && !sql.trim()) {
      setError("Write a query first, or switch back to Builder.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      // saving in Builder mode clears any SQL, so the filters take over again
      const payload = { name: name.trim(), filters, sql: mode === "sql" ? sql : "" };
      if (initial) await updateSegment(initial.id, payload);
      else await createSegment(payload);
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="info-row-editing" onSubmit={onSubmit}>
      <label htmlFor="seg-name">Segment name</label>
      <input id="seg-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Generator leads" autoFocus />

      <div className="editor-mode-tabs" role="tablist" aria-label="Segment type" style={{ marginTop: 10 }}>
        <button type="button" role="tab" aria-selected={mode === "builder"} className={mode === "builder" ? "active" : ""} onClick={() => setMode("builder")}>
          <ListFilter size={13} /> Builder
        </button>
        <button type="button" role="tab" aria-selected={mode === "sql"} className={mode === "sql" ? "active" : ""} onClick={() => setMode("sql")}>
          <Code2 size={13} /> SQL
        </button>
      </div>

      {mode === "sql" ? (
        <SqlSegmentEditor sql={sql} onChange={setSql} />
      ) : (
        <>
      <div className="card assistant-suggest-card">
        <label htmlFor="seg-describe">
          <Bot size={13} className="h3-icon" /> Describe who you want, and let the assistant set the filters
        </label>
        <div className="row">
          <input
            id="seg-describe"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g. leads interested in generators who haven't bought in 60 days"
            style={{ flex: 1 }}
          />
          <button type="button" onClick={onSuggest} disabled={suggesting || !description.trim()}>
            <Sparkles size={14} /> {suggesting ? "Thinking…" : "Suggest filters"}
          </button>
        </div>
        {appliedSummary && <p className="muted small">Applied: {appliedSummary} - adjust below if needed.</p>}
        <ErrorText message={suggestError} />
      </div>

      {catalog ? <SegmentQueryBuilder group={filters} catalog={catalog} onChange={setFilters} /> : <Spinner />}
        </>
      )}

      <div className="card" style={{ marginTop: 10 }}>
        {mode === "sql" && sqlError ? (
          <p className="small error-text" style={{ margin: 0 }}>
            {sqlError}
          </p>
        ) : (
          <p className="small" style={{ margin: 0 }}>
            {mode === "sql" && !sql.trim()
              ? "Matching customers will show here as you write."
              : preview
                ? `${preview.total} matching customer${preview.total === 1 ? "" : "s"}`
                : "Calculating…"}
          </p>
        )}
        {preview && preview.total > 0 && (
          <p className="muted small" style={{ margin: "4px 0 0" }}>
            {preview.members
              .slice(0, 5)
              .map((m) => m.name)
              .join(", ")}
            {preview.total > 5 ? `, +${preview.total - 5} more` : ""}
          </p>
        )}
      </div>

      <ErrorText message={error} />
      <div className="row" style={{ marginTop: 10 }}>
        <button type="submit" className="btn-primary" disabled={busy}>
          <Check size={15} /> Save
        </button>
        <button type="button" onClick={onCancel} disabled={busy}>
          <X size={15} /> Cancel
        </button>
      </div>
    </form>
  );
}
