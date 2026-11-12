import { Heart, Package, Receipt } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { listAllOrders, type OrderWithCustomer } from "../api/orders";
import { errorMessage } from "../api/errorMessage";
import { getSummary } from "../api/summary";
import type { InterestRollup } from "../api/types";
import ErrorText from "../components/ErrorText";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";
import { avatarStyle, initials } from "../utils/avatar";

function itemsToText(items: OrderWithCustomer["items"]): string {
  return items.map((i) => (i.qty && i.qty !== 1 ? `${i.name} x${i.qty}` : i.name)).join(", ") || "(no items)";
}

export default function OrdersPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const pending = searchParams.get("pending") === "true";

  const [orders, setOrders] = useState<OrderWithCustomer[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setOrders(null);
    listAllOrders({ pending })
      .then(setOrders)
      .catch((err) => setError(errorMessage(err)));
  }, [pending]);

  return (
    <div>
      <TopBar title="Orders" backTo="/dashboard" />

      <div className="page-actions">
        <div className="segmented" role="tablist" aria-label="Filter orders">
          <button type="button" role="tab" aria-selected={!pending} className={!pending ? "active" : ""} onClick={() => setSearchParams({}, { replace: true })}>
            All orders
          </button>
          <button type="button" role="tab" aria-selected={pending} className={pending ? "active" : ""} onClick={() => setSearchParams({ pending: "true" }, { replace: true })}>
            Awaiting delivery
          </button>
        </div>
      </div>

      <ErrorText message={error} />
      {!orders ? (
        <Spinner />
      ) : (
        orders.length === 0 ? (
          <p className="muted small page-note">{pending ? "No orders awaiting delivery." : "No orders yet."}</p>
        ) : (
          <div className="card-grid">
            {orders.map((o) => (
              <Link key={o.id} to={`/customers/${o.customer_id}?tab=orders`} className="card order-card">
                <div className="card-head" style={{ marginBottom: 6 }}>
                  <span className="avatar sm" style={avatarStyle(o.customer_name)} aria-hidden="true">
                    {initials(o.customer_name)}
                  </span>
                  <div className="card-head-text">
                    <div className="card-title">{o.customer_name}</div>
                    <div className="card-sub">{itemsToText(o.items) || "(no items)"}</div>
                  </div>
                  <span className={`badge ${o.delivered ? "badge-customer" : "badge-lead"}`}>{o.delivered ? "Delivered" : "Pending"}</span>
                </div>
                <div className="order-meta">
                  <span>Ordered {o.order_date}</span>
                  {o.delivery_date && <span>Due {o.delivery_date}</span>}
                  <span className={`badge ${o.paid ? "badge-customer" : "badge-inactive"}`}>{o.paid ? "Paid" : "Unpaid"}</span>
                </div>
              </Link>
            ))}
          </div>
        )
      )}

      <InterestedInSection />
    </div>
  );
}

function InterestedInSection() {
  const navigate = useNavigate();
  const [interests, setInterests] = useState<InterestRollup[] | null>(null);

  useEffect(() => {
    getSummary({}).then((s) => setInterests(s.interests));
  }, []);

  if (!interests || interests.length === 0) return null;

  return (
    <div className="card">
      <h3>
        <Heart size={15} className="h3-icon" /> Interested in
      </h3>
      <p className="muted small">Turn a stated interest straight into a sale.</p>
      {interests.map((i) => (
        <div key={i.interest} className="interest-convert-group">
          <b className="small">{i.interest}</b>
          {i.customers.map((c) => (
            <div key={c.id} className="row-between interest-convert-row">
              <Link to={`/customers/${c.id}`}>{c.name}</Link>
              <div className="row" style={{ gap: 4 }}>
                <button
                  type="button"
                  className="icon-btn btn-ghost"
                  title="New order"
                  aria-label={`New order for ${c.name}`}
                  onClick={() => navigate(`/customers/${c.id}?tab=orders&new=1`)}
                >
                  <Package size={14} />
                </button>
                <button
                  type="button"
                  className="icon-btn btn-ghost"
                  title="New transaction"
                  aria-label={`New transaction for ${c.name}`}
                  onClick={() => navigate(`/customers/${c.id}?tab=transactions&new=1`)}
                >
                  <Receipt size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
