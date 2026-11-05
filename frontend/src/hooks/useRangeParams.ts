import { useSearchParams } from "react-router-dom";
import { presetRange, type RangePreset } from "../utils/dateRange";

export function useRangeParams() {
  const [searchParams, setSearchParams] = useSearchParams();
  const preset = (searchParams.get("preset") as RangePreset) || "all";
  const customFrom = searchParams.get("from") || "";
  const customTo = searchParams.get("to") || "";

  function setPreset(p: RangePreset) {
    const next = new URLSearchParams(searchParams);
    next.set("preset", p);
    setSearchParams(next, { replace: true });
  }
  function setCustomFrom(v: string) {
    const next = new URLSearchParams(searchParams);
    next.set("from", v);
    next.set("preset", "custom");
    setSearchParams(next, { replace: true });
  }
  function setCustomTo(v: string) {
    const next = new URLSearchParams(searchParams);
    next.set("to", v);
    next.set("preset", "custom");
    setSearchParams(next, { replace: true });
  }

  const range = presetRange(preset, customFrom, customTo);

  const queryString = (() => {
    const q = new URLSearchParams();
    q.set("preset", preset);
    if (preset === "custom") {
      if (customFrom) q.set("from", customFrom);
      if (customTo) q.set("to", customTo);
    }
    return q.toString();
  })();

  return { preset, customFrom, customTo, setPreset, setCustomFrom, setCustomTo, range, queryString };
}
