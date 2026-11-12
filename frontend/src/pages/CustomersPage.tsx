import { Search, UserRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { listCustomers } from "../api/customers";
import { errorMessage } from "../api/errorMessage";
import type { Customer, CustomerStatus } from "../api/types";
import ErrorText from "../components/ErrorText";
import Pagination from "../components/Pagination";
import Spinner from "../components/Spinner";
import StatusBadge from "../components/StatusBadge";
import TopBar from "../components/TopBar";

const PAGE_SIZE = 50;

export default function CustomersPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<CustomerStatus | "">((searchParams.get("status") as CustomerStatus | "") || "");
  // the page lives in the URL, so going into a customer and back returns to it
  const page = Math.max(1, Number(searchParams.get("page")) || 1);

  function goToPage(next: number) {
    setSearchParams(
      (params) => {
        const updated = new URLSearchParams(params);
        if (next <= 1) updated.delete("page");
        else updated.set("page", String(next));
        return updated;
      },
      { replace: false }
    );
    window.scrollTo({ top: 0 });
  }

  function onSearch(value: string) {
    setSearch(value);
    if (page !== 1) goToPage(1);
  }

  function onStatus(value: CustomerStatus | "") {
    setStatus(value);
    if (page !== 1) goToPage(1);
  }
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const lastSearch = useRef(search);

  useEffect(() => {
    // show the spinner straight away, so the previous page's customers are
    // never on screen under the new page's numbers; only typing is debounced
    setLoading(true);
    const typing = lastSearch.current !== search;
    lastSearch.current = search;
    const handle = setTimeout(() => {
      setError(null);
      listCustomers({ search, status, page, pageSize: PAGE_SIZE })
        .then((res) => {
          // a page number past the end (e.g. after deleting customers) falls back to the last page
          const last = Math.max(1, Math.ceil(res.total / PAGE_SIZE));
          if (page > last) {
            goToPage(last);
            return;
          }
          setCustomers(res.items);
          setTotal(res.total);
        })
        .catch((err) => setError(errorMessage(err)))
        .finally(() => setLoading(false));
    }, typing ? 250 : 0);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, status, page]);

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
            onChange={(e) => onSearch(e.target.value)}
          />
        </div>
        <select aria-label="Filter by status" value={status} onChange={(e) => onStatus(e.target.value as CustomerStatus | "")}>
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

      {!loading && <Pagination page={page} pageSize={PAGE_SIZE} total={total} onChange={goToPage} />}
    </div>
  );
}
