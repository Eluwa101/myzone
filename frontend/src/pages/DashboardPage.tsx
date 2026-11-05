import { CalendarRange, Heart, MessageCircleQuestion, Trophy, Users, Wallet } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
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
      <Link to="/ask" className="card ask-data-link">
        <MessageCircleQuestion size={18} />
        <div>
          <b>Ask your data</b>
          <div className="muted small">Read-only questions about your customers and sales</div>
        </div>
      </Link>
      <ErrorText message={error} />
      {!summary ? (
        <Spinner />
      ) : (
        <>
          <div className="stat-grid">
            <div className="card stat-card">
              <div className="stat-icon">
                <Users size={18} />
              </div>
              <div className="stat-value">{summary.total_customers}</div>
              <div className="stat-label">
                customers
                {summary.without_consent > 0 && ` · ${summary.without_consent} w/o consent`}
              </div>
            </div>
            <div className="card stat-card">
              <div className="stat-icon">
                <Wallet size={18} />
              </div>
              <div className="stat-value stat-value-money">{fmtCurrencyMap(summary.this_month_by_currency)}</div>
              <div className="stat-label">this month · all-time {fmtCurrencyMap(summary.all_time_by_currency)}</div>
            </div>
          </div>

          <div className="card">
            <h3>
              <CalendarRange size={15} className="h3-icon" /> Last 6 months
            </h3>
            {summary.last_6_months.map((m) => (
              <div key={m.month} className="row-between">
                <span className="muted small">{m.month}</span>
                <span>{fmtCurrencyMap(m.totals)}</span>
              </div>
            ))}
          </div>

          <div className="card">
            <h3>
              <Trophy size={15} className="h3-icon" /> Top customers
            </h3>
            {summary.top_customers.length === 0 ? (
              <p className="muted small">No transactions yet.</p>
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
            <h3>
              <Heart size={15} className="h3-icon" /> Interested in
            </h3>
            {summary.interests.length === 0 ? (
              <p className="muted small">No interests recorded.</p>
            ) : (
              summary.interests.map((i) => (
                <div key={i.interest} className="row-between" style={{ alignItems: "flex-start" }}>
                  <b>{i.interest}</b>
                  <span className="muted small" style={{ textAlign: "right" }}>
                    ({i.customers.length}) {i.customers.join(", ")}
                  </span>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
