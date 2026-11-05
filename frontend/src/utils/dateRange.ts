export type RangePreset = "month" | "6m" | "all" | "custom";

function toIso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function presetRange(preset: RangePreset, customFrom?: string, customTo?: string): { startDate?: string; endDate?: string } {
  const today = new Date();
  if (preset === "all") return {};
  if (preset === "month") {
    return { startDate: toIso(new Date(today.getFullYear(), today.getMonth(), 1)), endDate: toIso(today) };
  }
  if (preset === "6m") {
    return { startDate: toIso(new Date(today.getFullYear(), today.getMonth() - 5, 1)), endDate: toIso(today) };
  }
  return { startDate: customFrom || undefined, endDate: customTo || undefined };
}

export function presetLabel(preset: RangePreset, customFrom?: string, customTo?: string): string {
  if (preset === "month") return "This month";
  if (preset === "6m") return "Last 6 months";
  if (preset === "all") return "All time";
  return customFrom && customTo ? `${customFrom} – ${customTo}` : "Custom range";
}

export const PRESET_OPTIONS: { value: RangePreset; label: string }[] = [
  { value: "month", label: "This month" },
  { value: "6m", label: "Last 6 months" },
  { value: "all", label: "All time" },
  { value: "custom", label: "Custom" },
];
