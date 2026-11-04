import { useEffect, useState } from "react";
import { getSummary } from "../api/summary";
import { errorMessage } from "../api/errorMessage";
import type { Summary } from "../api/types";
import ErrorText from "../components/ErrorText";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";

function fmtCurrencyMap(m: Record<string, number>): string {
  const entries = Object.entries(m);
  if (!entries.length) return "0.00";
  return entries.map(([cur, v]) => `${cur ? cur + " " : ""}${v.toLocaleString(undefined, { minimumFractionDigits: 2 })}`).join(" + ");
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSummary()
      .then(setSummary)
      .catch((err) => setError(errorMessage(err)));
  }, []);

  return (
    <div>
      <TopBar title="Dashboard" />
      <ErrorText message={error} />
      {!summary ? (
        <Spinner />
      ) : (
        <>
          <div className="card">
            <b>{summary.total_customers} customers</b>
            {summary.without_consent > 0 && <span className="muted"> ({summary.without_consent} without consent recorded)</span>}
            <div className="muted small">
              {Object.entries(summary.status_counts)
                .map(([k, v]) => `${k}: ${v}`)
                .join(" · ")}
            </div>
          </div>

          <div className="card">
            <div className="muted small">All-time sales</div>
            <b>{fmtCurrencyMap(summary.all_time_by_currency)}</b>
            <div className="muted small" style={{ marginTop: 6 }}>
              This month
            </div>
            <b>{fmtCurrencyMap(summary.this_month_by_currency)}</b>
          </div>

          <div className="card">
            <h3>Last 6 months</h3>
            {summary.last_6_months.map((m) => (
              <div key={m.month} className="row-between">
                <span>{m.month}</span>
                <span>{fmtCurrencyMap(m.totals)}</span>
              </div>
            ))}
          </div>

          <div className="card">
            <h3>Top customers</h3>
            {summary.top_customers.length === 0 ? (
              <p className="muted">No transactions yet.</p>
            ) : (
              summary.top_customers.map((c, i) => (
                <div key={`${c.customer_id}-${i}`} className="row-between">
                  <span>{c.name}</span>
                  <span>
                    {c.currency} {c.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
              ))
            )}
          </div>

          <div className="card">
            <h3>Interested in</h3>
            {summary.interests.length === 0 ? (
              <p className="muted">No interests recorded.</p>
            ) : (
              summary.interests.map((i) => (
                <div key={i.interest} style={{ marginTop: 6 }}>
                  <b>{i.interest}</b> <span className="muted small">({i.customers.length}) {i.customers.join(", ")}</span>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
