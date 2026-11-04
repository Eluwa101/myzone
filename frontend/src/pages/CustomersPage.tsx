import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listCustomers } from "../api/customers";
import { errorMessage } from "../api/errorMessage";
import type { Customer, CustomerStatus } from "../api/types";
import ErrorText from "../components/ErrorText";
import Spinner from "../components/Spinner";
import StatusBadge from "../components/StatusBadge";
import TopBar from "../components/TopBar";

function totalsLabel(c: Customer): string {
  const totals: Record<string, number> = {};
  for (const t of c.transactions) {
    const value = (t.amount || 0) * (t.qty || 1);
    totals[t.currency || ""] = (totals[t.currency || ""] || 0) + value;
  }
  const parts = Object.entries(totals).map(([cur, v]) => `${cur ? cur + " " : ""}${v.toLocaleString(undefined, { minimumFractionDigits: 2 })}`);
  return parts.length ? parts.join(" + ") : "0.00";
}

export default function CustomersPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<CustomerStatus | "">("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handle = setTimeout(() => {
      setLoading(true);
      setError(null);
      listCustomers({ search, status, pageSize: 50 })
        .then((res) => {
          setCustomers(res.items);
          setTotal(res.total);
        })
        .catch((err) => setError(errorMessage(err)))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(handle);
  }, [search, status]);

  return (
    <div>
      <TopBar title="Customers" />
      <div className="toolbar">
        <input
          aria-label="Search customers"
          className="search-input"
          placeholder="Search name, job, pet, phone…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value as CustomerStatus | "")}>
          <option value="">All statuses</option>
          <option value="lead">Lead</option>
          <option value="customer">Customer</option>
          <option value="inactive">Inactive</option>
        </select>
      </div>

      <ErrorText message={error} />
      {loading ? (
        <Spinner />
      ) : customers.length === 0 ? (
        <p className="muted empty-state">No customers yet. Tap "+ New customer" to add the first one.</p>
      ) : (
        <ul className="customer-list">
          {customers.map((c) => (
            <li key={c.id}>
              <Link to={`/customers/${c.id}`} className="card customer-card">
                <div className="customer-card-top">
                  <b>{c.name}</b>
                  <StatusBadge status={c.status} />
                </div>
                <div className="muted small">
                  {[c.job, c.nationality, c.pet && `Pet: ${c.pet}`, c.phone, c.interests && `Interested in: ${c.interests}`]
                    .filter(Boolean)
                    .join(" · ")}
                </div>
                <div className="muted small">
                  {totalsLabel(c)} · {c.transactions.length} txn
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {!loading && <p className="muted small">{total} total</p>}
      <Link to="/customers/new" className="fab" aria-label="New customer">
        +
      </Link>
    </div>
  );
}
