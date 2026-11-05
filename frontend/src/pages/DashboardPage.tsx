import { Download, Heart, MessageCircleQuestion, RefreshCw, Trash2, Trophy, Users, Wallet } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { askData } from "../api/agent";
import { getSummary } from "../api/summary";
import { errorMessage } from "../api/errorMessage";
import type { SavedWidget, Summary } from "../api/types";
import { deleteWidget, listWidgets } from "../api/widgets";
import DashboardRangeFilter from "../components/DashboardRangeFilter";
import ErrorText from "../components/ErrorText";
import MarkdownMessage from "../components/MarkdownMessage";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";
import { useRangeParams } from "../hooks/useRangeParams";
import { downloadCsv } from "../utils/exportCsv";
import { presetLabel } from "../utils/dateRange";

function fmtCurrencyMap(m: Record<string, number>): string {
  const entries = Object.entries(m);
  if (!entries.length) return "0.00";
  return entries.map(([cur, v]) => `${cur ? cur + " " : ""}${v.toLocaleString(undefined, { minimumFractionDigits: 2 })}`).join(" + ");
}

export default function DashboardPage() {
  const { preset, customFrom, customTo, setPreset, setCustomFrom, setCustomTo, range, queryString } = useRangeParams();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSummary(null);
    getSummary(range)
      .then(setSummary)
      .catch((err) => setError(errorMessage(err)));
  }, [range.startDate, range.endDate]);

  const label = presetLabel(preset, customFrom, customTo);

  function onExport() {
    if (!summary) return;
    const rows: unknown[][] = [
      ["Range", "Label", label],
      ["Customers", "Total", summary.total_customers],
      ["Customers", "Without consent", summary.without_consent],
      ...Object.entries(summary.status_counts).map(([k, v]) => ["Customers by status", k, v]),
      ...Object.entries(summary.all_time_by_currency).map(([k, v]) => ["Sales total", k, v]),
      ...summary.last_6_months.flatMap((m) => Object.entries(m.totals).map(([cur, v]) => ["Monthly breakdown", `${m.month} ${cur}`, v])),
      ...summary.top_customers.map((c) => ["Top customer", `${c.name} (${c.currency})`, c.total]),
      ...summary.interests.map((i) => ["Interest", i.interest, i.customers.join(" | ")]),
    ];
    downloadCsv(`dashboard-summary-${preset}.csv`, ["Section", "Key", "Value"], rows);
  }

  return (
    <div>
      <TopBar
        title="Dashboard"
        actions={
          summary && (
            <button type="button" className="icon-btn btn-ghost" aria-label="Export summary" title="Export summary as CSV" onClick={onExport}>
              <Download size={18} />
            </button>
          )
        }
      />
      <Link to="/ask" className="card ask-data-link">
        <MessageCircleQuestion size={18} />
        <div>
          <b>Ask your data</b>
          <div className="muted small">Read-only questions about your customers and sales</div>
        </div>
      </Link>

      <DashboardRangeFilter
        preset={preset}
        customFrom={customFrom}
        customTo={customTo}
        onPresetChange={setPreset}
        onCustomFromChange={setCustomFrom}
        onCustomToChange={setCustomTo}
      />

      <ErrorText message={error} />
      {!summary ? (
        <Spinner />
      ) : (
        <>
          <div className="stat-grid">
            <Link to={`/customers?${queryString}`} className="card stat-card">
              <div className="stat-icon">
                <Users size={18} />
              </div>
              <div className="stat-value">{summary.total_customers}</div>
              <div className="stat-label">
                customers · {label}
                {summary.without_consent > 0 && ` · ${summary.without_consent} w/o consent`}
              </div>
            </Link>
            <div className="card stat-card">
              <div className="stat-icon">
                <Wallet size={18} />
              </div>
              <div className="stat-value stat-value-money">{fmtCurrencyMap(summary.all_time_by_currency)}</div>
              <div className="stat-label">sales · {label}</div>
            </div>
          </div>

          {Object.entries(summary.status_counts).length > 0 && (
            <div className="card">
              <h3>Customers by status · {label}</h3>
              {Object.entries(summary.status_counts).map(([status, count]) => (
                <Link key={status} to={`/customers?status=${status}`} className="row-between">
                  <span className="muted small" style={{ textTransform: "capitalize" }}>
                    {status}
                  </span>
                  <span>{count}</span>
                </Link>
              ))}
            </div>
          )}

          <div className="card">
            <div className="row-between" style={{ borderBottom: "none", paddingBottom: 4 }}>
              <h3 style={{ margin: 0 }}>Monthly breakdown</h3>
              <Link to={`/dashboard/monthly?${queryString}`} className="muted small">
                View full →
              </Link>
            </div>
            {summary.last_6_months.map((m) => (
              <div key={m.month} className="row-between">
                <span className="muted small">{m.month}</span>
                <span>{fmtCurrencyMap(m.totals)}</span>
              </div>
            ))}
          </div>

          <div className="card">
            <div className="row-between" style={{ borderBottom: "none", paddingBottom: 4 }}>
              <h3 style={{ margin: 0 }}>
                <Trophy size={15} className="h3-icon" /> Top customers
              </h3>
              <Link to={`/dashboard/top-customers?${queryString}`} className="muted small">
                View all →
              </Link>
            </div>
            {summary.top_customers.length === 0 ? (
              <p className="muted small">No transactions yet.</p>
            ) : (
              summary.top_customers.map((c, i) => (
                <Link key={`${c.customer_id}-${i}`} to={`/customers/${c.customer_id}?tab=transactions`} className="row-between">
                  <span>{c.name}</span>
                  <span>
                    {c.currency} {c.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </Link>
              ))
            )}
          </div>

          <div className="card">
            <div className="row-between" style={{ borderBottom: "none", paddingBottom: 4 }}>
              <h3 style={{ margin: 0 }}>
                <Heart size={15} className="h3-icon" /> Interested in
              </h3>
              <Link to={`/dashboard/interests?${queryString}`} className="muted small">
                View all →
              </Link>
            </div>
            {summary.interests.length === 0 ? (
              <p className="muted small">No interests recorded.</p>
            ) : (
              summary.interests.slice(0, 5).map((i) => (
                <div key={i.interest} className="row-between" style={{ alignItems: "flex-start" }}>
                  <b>{i.interest}</b>
                  <span className="muted small" style={{ textAlign: "right" }}>
                    ({i.customers.length}) {i.customers.join(", ")}
                  </span>
                </div>
              ))
            )}
          </div>

          <SavedWidgets />
        </>
      )}
    </div>
  );
}

function SavedWidgets() {
  const [widgets, setWidgets] = useState<SavedWidget[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listWidgets()
      .then(setWidgets)
      .finally(() => setLoading(false));
  }, []);

  async function remove(id: string) {
    await deleteWidget(id);
    setWidgets((w) => w.filter((x) => x.id !== id));
  }

  if (loading || widgets.length === 0) return null;

  return (
    <div className="card">
      <h3>Saved questions</h3>
      {widgets.map((w) => (
        <SavedWidgetRow key={w.id} widget={w} onDelete={() => remove(w.id)} />
      ))}
    </div>
  );
}

function SavedWidgetRow({ widget, onDelete }: { widget: SavedWidget; onDelete: () => void }) {
  const [answer, setAnswer] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function run() {
    setBusy(true);
    setError(null);
    askData(widget.question)
      .then((r) => setAnswer(r.answer))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setBusy(false));
  }

  useEffect(run, [widget.question]);

  return (
    <div className="note-card" style={{ borderTop: "1px solid var(--border)", paddingTop: 12, marginTop: 4 }}>
      <div className="row-between" style={{ borderBottom: "none" }}>
        <b className="small">{widget.title}</b>
        <div className="row">
          <button type="button" className="icon-btn btn-ghost" aria-label="Refresh" onClick={run} disabled={busy}>
            <RefreshCw size={14} />
          </button>
          <button type="button" className="icon-btn btn-ghost" aria-label="Delete widget" onClick={onDelete}>
            <Trash2 size={14} />
          </button>
        </div>
      </div>
      {busy && <p className="muted small">Thinking…</p>}
      <ErrorText message={error} />
      {answer && <MarkdownMessage content={answer} />}
    </div>
  );
}
