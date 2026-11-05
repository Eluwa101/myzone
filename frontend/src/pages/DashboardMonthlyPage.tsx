import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { getMonthly } from "../api/summary";
import { errorMessage } from "../api/errorMessage";
import type { MonthTotal } from "../api/types";
import DashboardRangeFilter from "../components/DashboardRangeFilter";
import ErrorText from "../components/ErrorText";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";
import { useRangeParams } from "../hooks/useRangeParams";
import { presetLabel } from "../utils/dateRange";
import { downloadCsv } from "../utils/exportCsv";

function fmtCurrencyMap(m: Record<string, number>): string {
  const entries = Object.entries(m);
  if (!entries.length) return "0.00";
  return entries.map(([cur, v]) => `${cur ? cur + " " : ""}${v.toLocaleString(undefined, { minimumFractionDigits: 2 })}`).join(" + ");
}

export default function DashboardMonthlyPage() {
  const { preset, customFrom, customTo, setPreset, setCustomFrom, setCustomTo, range } = useRangeParams();
  const [months, setMonths] = useState<MonthTotal[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setMonths(null);
    getMonthly(range)
      .then(setMonths)
      .catch((err) => setError(errorMessage(err)));
  }, [range.startDate, range.endDate]);

  function onExport() {
    if (!months) return;
    const currencies = Array.from(new Set(months.flatMap((m) => Object.keys(m.totals))));
    downloadCsv(
      "monthly-breakdown.csv",
      ["Month", ...currencies],
      months.map((m) => [m.month, ...currencies.map((cur) => m.totals[cur] ?? 0)])
    );
  }

  return (
    <div>
      <TopBar
        title="Monthly breakdown"
        backTo="/dashboard"
        actions={
          months &&
          months.length > 0 && (
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
      {!months ? (
        <Spinner />
      ) : (
        <div className="card">
          {months.length === 0 ? (
            <p className="muted small">No transactions in this range.</p>
          ) : (
            months.map((m) => (
              <div key={m.month} className="row-between">
                <span className="muted small">{m.month}</span>
                <span>{fmtCurrencyMap(m.totals)}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
