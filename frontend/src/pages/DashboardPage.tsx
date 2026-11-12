import { BarChart3, Download, Heart, MessageCircleQuestion, PackageSearch, RefreshCw, Trash2, Trophy, Users, UsersRound, Wallet } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { askData } from "../api/agent";
import { listAllOrders, type OrderWithCustomer } from "../api/orders";
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

function sumValues(m: Record<string, number>): number {
  return Object.values(m).reduce((a, b) => a + b, 0);
}

function fmtCurrencyMap(m: Record<string, number>): string {
  const entries = Object.entries(m);
  if (!entries.length) return "0.00";
  return entries.map(([cur, v]) => `${cur ? cur + " " : ""}${v.toLocaleString(undefined, { minimumFractionDigits: 2 })}`).join(" + ");
}

export default function DashboardPage() {
  const { preset, customFrom, customTo, setPreset, setCustomFrom, setCustomTo, range, queryString } = useRangeParams();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<OrderWithCustomer[] | null>(null);

  useEffect(() => {
    listAllOrders({ pending: true })
      .then(setPending)
      .catch(() => setPending([]));
  }, []);

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
      <div className="dash-toolbar">
        <DashboardRangeFilter
          preset={preset}
          customFrom={customFrom}
          customTo={customTo}
          onPresetChange={setPreset}
          onCustomFromChange={setCustomFrom}
          onCustomToChange={setCustomTo}
        />
        <Link to="/ask" className="pill-link ask-pill">
          <MessageCircleQuestion size={15} /> Ask your data
        </Link>
      </div>

      <ErrorText message={error} />
      {!summary ? (
        <Spinner />
      ) : (
        <div className="dash">
          <div className="dash-kpis">
            <Link to={`/customers?${queryString}`} className="card kpi">
              <span className="card-icon tone-blue" aria-hidden="true">
                <Users />
              </span>
              <div>
                <div className="kpi-value">{summary.total_customers}</div>
                <div className="kpi-label">
                  customers · {label}
                  {summary.without_consent > 0 && ` · ${summary.without_consent} w/o consent`}
                </div>
              </div>
            </Link>
            <div className="card kpi">
              <span className="card-icon tone-teal" aria-hidden="true">
                <Wallet />
              </span>
              <div>
                <div className="kpi-value kpi-money">{fmtCurrencyMap(summary.all_time_by_currency)}</div>
                <div className="kpi-label">sales · {label}</div>
              </div>
            </div>
            <Link to="/orders?pending=true" className="card kpi">
              <span className="card-icon tone-amber" aria-hidden="true">
                <PackageSearch />
              </span>
              <div>
                <div className="kpi-value">{pending ? pending.length : "–"}</div>
                <div className="kpi-label">orders awaiting delivery</div>
              </div>
            </Link>
            <div className="card kpi">
              <span className="card-icon tone-violet" aria-hidden="true">
                <UsersRound />
              </span>
              <div className="kpi-status">
                <div className="kpi-label" style={{ marginBottom: 5 }}>
                  customers by status
                </div>
                <div className="kpi-pills">
                  {Object.entries(summary.status_counts).length === 0 && <span className="muted small">None yet</span>}
                  {Object.entries(summary.status_counts).map(([status, count]) => (
                    <Link key={status} to={`/customers?status=${status}`} className={`badge badge-${status}`}>
                      {status} {count}
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="dash-main">
            <div className="card">
              <div className="card-head">
                <span className="card-icon tone-blue" aria-hidden="true">
                  <BarChart3 />
                </span>
                <div className="card-head-text">
                  <div className="card-title">Monthly breakdown</div>
                  <div className="card-sub">sales per month</div>
                </div>
                <Link to={`/dashboard/monthly?${queryString}`} className="muted small">
                  View full →
                </Link>
              </div>
              {summary.last_6_months.length === 0 ? (
                <p className="muted small">No sales yet.</p>
              ) : (
                <div className="month-bars">
                  {(() => {
                    const max = Math.max(1, ...summary.last_6_months.map((m) => sumValues(m.totals)));
                    return summary.last_6_months.map((m) => (
                      <div key={m.month} className="month-row">
                        <span className="month-label">{m.month}</span>
                        <div className="bar-track">
                          <div className="bar-fill" style={{ width: `${Math.max(2, (sumValues(m.totals) / max) * 100)}%` }} />
                        </div>
                        <span className="month-amt">{fmtCurrencyMap(m.totals)}</span>
                      </div>
                    ));
                  })()}
                </div>
              )}
            </div>
            <PendingOrdersCard orders={pending} />
          </div>

          <div className="dash-lists">
            <div className="card">
              <div className="card-head">
                <span className="card-icon tone-amber" aria-hidden="true">
                  <Trophy />
                </span>
                <div className="card-head-text">
                  <div className="card-title">Top customers</div>
                </div>
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
                    <span className="small">
                      {c.currency} {c.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </Link>
                ))
              )}
            </div>

            <div className="card">
              <div className="card-head">
                <span className="card-icon tone-rose" aria-hidden="true">
                  <Heart />
                </span>
                <div className="card-head-text">
                  <div className="card-title">Interested in</div>
                </div>
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
                      ({i.customers.length}){" "}
                      {i.customers.map((c, idx) => (
                        <span key={c.id}>
                          {idx > 0 && ", "}
                          <Link to={`/customers/${c.id}`}>{c.name}</Link>
                        </span>
                      ))}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          <SavedWidgets />
        </div>
      )}
    </div>
  );
}

function PendingOrdersCard({ orders }: { orders: OrderWithCustomer[] | null }) {
  const today = new Date().toISOString().slice(0, 10);
  return (
    <div className="card">
      <div className="card-head">
        <span className="card-icon tone-amber" aria-hidden="true">
          <PackageSearch />
        </span>
        <div className="card-head-text">
          <div className="card-title">Orders awaiting delivery</div>
          <div className="card-sub">{orders ? `${orders.length} open` : "loading…"}</div>
        </div>
        <Link to="/orders?pending=true" className="muted small">
          View all →
        </Link>
      </div>
      {orders && orders.length === 0 && <p className="muted small">Nothing is waiting for delivery.</p>}
      {(orders ?? []).slice(0, 6).map((order) => {
        const due = order.delivery_date;
        const overdue = !!due && due < today;
        return (
          <Link key={order.id} to={`/customers/${order.customer_id}?tab=orders`} className="row-between">
            <span>{order.customer_name}</span>
            <span className={`small ${overdue ? "overdue" : "muted"}`}>
              {due ? `${overdue ? "Overdue · " : "Due "}${due}` : `Ordered ${order.order_date}`}
            </span>
          </Link>
        );
      })}
      {orders && orders.length > 6 && (
        <p className="muted small" style={{ margin: "6px 0 0" }}>
          and {orders.length - 6} more…
        </p>
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
