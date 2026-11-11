import { Search, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { listCustomers } from "../api/customers";
import { errorMessage } from "../api/errorMessage";
import type { Customer, CustomerStatus } from "../api/types";
import ErrorText from "../components/ErrorText";
import Spinner from "../components/Spinner";
import StatusBadge from "../components/StatusBadge";
import TopBar from "../components/TopBar";

export default function CustomersPage() {
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<CustomerStatus | "">((searchParams.get("status") as CustomerStatus | "") || "");
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
        <div className="search-wrap">
          <Search size={16} className="search-icon" aria-hidden="true" />
          <input
            aria-label="Search customers"
            className="search-input"
            placeholder="Search name, job, pet, phone, ID, item bought…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
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
        <div className="empty-state">
          <UserRound size={40} className="empty-state-icon" strokeWidth={1.5} />
          <p>No customers yet. Tap the + button to add the first one.</p>
        </div>
      ) : (
        <ul className="customer-list">
          {customers.map((c) => (
            <li key={c.id}>
              <Link to={`/customers/${c.id}`} className="card customer-card">
                <div className="customer-card-top">
                  <b>
                    {c.name}
                    {c.orders.some((o) => !o.delivered) && (
                      <span className="pending-order-dot" title="Has an order awaiting delivery" aria-label="Has an order awaiting delivery" />
                    )}
                  </b>
                  <StatusBadge status={c.status} />
                </div>
                <div className="muted small">
                  <span className="customer-display-id">{c.display_id}</span> · {c.transactions.length} transaction
                  {c.transactions.length === 1 ? "" : "s"}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {!loading && <p className="muted small page-note">{total} total</p>}
    </div>
  );
}
