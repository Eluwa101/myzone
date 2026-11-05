import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getSummary } from "../api/summary";
import { errorMessage } from "../api/errorMessage";
import type { InterestRollup } from "../api/types";
import DashboardRangeFilter from "../components/DashboardRangeFilter";
import ErrorText from "../components/ErrorText";
import Spinner from "../components/Spinner";
import TopBar from "../components/TopBar";
import { useRangeParams } from "../hooks/useRangeParams";
import { presetLabel } from "../utils/dateRange";
import { downloadCsv } from "../utils/exportCsv";

export default function DashboardInterestsPage() {
  const { preset, customFrom, customTo, setPreset, setCustomFrom, setCustomTo, range } = useRangeParams();
  const [interests, setInterests] = useState<InterestRollup[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setInterests(null);
    getSummary(range)
      .then((s) => setInterests(s.interests))
      .catch((err) => setError(errorMessage(err)));
  }, [range.startDate, range.endDate]);

  function onExport() {
    if (!interests) return;
    downloadCsv(
      "interests.csv",
      ["Interest", "Customer count", "Customers"],
      interests.map((i) => [i.interest, i.customers.length, i.customers.map((c) => c.name).join("; ")])
    );
  }

  return (
    <div>
      <TopBar
        title="Interested in"
        backTo="/dashboard"
        actions={
          interests &&
          interests.length > 0 && (
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
      {!interests ? (
        <Spinner />
      ) : (
        <div className="card">
          {interests.length === 0 ? (
            <p className="muted small">No interests recorded.</p>
          ) : (
            interests.map((i) => (
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
      )}
    </div>
  );
}
