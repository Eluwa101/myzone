import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getTopCustomers } from "../api/summary";
import { errorMessage } from "../api/errorMessage";
import type { TopCustomer } from "../api/types";
import DashboardRangeFilter from "../components/DashboardRangeFilter";
import ErrorText from "../components/ErrorText";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";
import { useRangeParams } from "../hooks/useRangeParams";
import { presetLabel } from "../utils/dateRange";
import { downloadCsv } from "../utils/exportCsv";

export default function DashboardTopCustomersPage() {
  const { preset, customFrom, customTo, setPreset, setCustomFrom, setCustomTo, range } = useRangeParams();
  const [items, setItems] = useState<TopCustomer[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setItems(null);
    getTopCustomers(range, 100)
      .then(setItems)
      .catch((err) => setError(errorMessage(err)));
  }, [range.startDate, range.endDate]);

  function onExport() {
    if (!items) return;
    downloadCsv(
      "top-customers.csv",
      ["Customer", "Currency", "Total"],
      items.map((c) => [c.name, c.currency, c.total])
    );
  }

  return (
    <div>
      <TopBar
        title="Top customers"
        backTo="/dashboard"
        actions={
          items &&
          items.length > 0 && (
            <button type="button" className="icon-btn btn-ghost" aria-label="Export" onClick={onExport}>
              <Download size={18} />
            </button>
          )
        }
      />
      <DashboardRangeFilter
        preset={preset}
        customFrom={customFrom}
        customTo={customTo}
        onPresetChange={setPreset}
        onCustomFromChange={setCustomFrom}
        onCustomToChange={setCustomTo}
      />
      <p className="muted small page-note">{presetLabel(preset, customFrom, customTo)}</p>
      <ErrorText message={error} />
      {!items ? (
        <Spinner />
      ) : (
        <div className="card">
          {items.length === 0 ? (
            <p className="muted small">No transactions in this range.</p>
          ) : (
            items.map((c, i) => (
              <Link key={`${c.customer_id}-${i}`} to={`/customers/${c.customer_id}?tab=transactions`} className="row-between">
                <span>{c.name}</span>
                <span>
                  {c.currency} {c.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </span>
              </Link>
            ))
          )}
        </div>
      )}
    </div>
  );
}
