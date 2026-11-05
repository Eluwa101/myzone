import { PRESET_OPTIONS, type RangePreset } from "../utils/dateRange";

export default function DashboardRangeFilter({
  preset,
  customFrom,
  customTo,
  onPresetChange,
  onCustomFromChange,
  onCustomToChange,
}: {
  preset: RangePreset;
  customFrom: string;
  customTo: string;
  onPresetChange: (p: RangePreset) => void;
  onCustomFromChange: (v: string) => void;
  onCustomToChange: (v: string) => void;
}) {
  return (
    <div className="card">
      <div className="row">
        {PRESET_OPTIONS.map((p) => (
          <button key={p.value} type="button" className={preset === p.value ? "btn-primary" : ""} onClick={() => onPresetChange(p.value)}>
            {p.label}
          </button>
        ))}
      </div>
      {preset === "custom" && (
        <div className="tx-edit-grid" style={{ marginTop: 10 }}>
          <div>
            <label htmlFor="range-from">From</label>
            <input id="range-from" type="date" value={customFrom} onChange={(e) => onCustomFromChange(e.target.value)} />
          </div>
          <div>
            <label htmlFor="range-to">To</label>
            <input id="range-to" type="date" value={customTo} onChange={(e) => onCustomToChange(e.target.value)} />
          </div>
        </div>
      )}
    </div>
  );
}
