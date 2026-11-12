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
    <div className="range-filter">
      <div className="segmented" role="tablist" aria-label="Date range">
        {PRESET_OPTIONS.map((p) => (
          <button
            key={p.value}
            type="button"
            role="tab"
            aria-selected={preset === p.value}
            className={preset === p.value ? "active" : ""}
            onClick={() => onPresetChange(p.value)}
          >
            {p.label}
          </button>
        ))}
      </div>
      {preset === "custom" && (
        <div className="range-custom">
          <label htmlFor="range-from">From</label>
          <input id="range-from" type="date" value={customFrom} onChange={(e) => onCustomFromChange(e.target.value)} />
          <label htmlFor="range-to">To</label>
          <input id="range-to" type="date" value={customTo} onChange={(e) => onCustomToChange(e.target.value)} />
        </div>
      )}
    </div>
  );
}
