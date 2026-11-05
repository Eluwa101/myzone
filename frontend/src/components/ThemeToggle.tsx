import { Monitor, Moon, Sun } from "lucide-react";
import { useState } from "react";
import { applyTheme, getStoredTheme, type ThemePref } from "../utils/theme";

const OPTIONS: { value: ThemePref; label: string; Icon: typeof Sun }[] = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "dark", label: "Dark", Icon: Moon },
  { value: "system", label: "System", Icon: Monitor },
];

export default function ThemeToggle() {
  const [pref, setPref] = useState<ThemePref>(getStoredTheme());

  function choose(value: ThemePref) {
    setPref(value);
    applyTheme(value);
  }

  return (
    <div className="tabs">
      {OPTIONS.map(({ value, label, Icon }) => (
        <button key={value} type="button" className={`tab-btn${pref === value ? " active" : ""}`} onClick={() => choose(value)}>
          <Icon size={14} /> {label}
        </button>
      ))}
    </div>
  );
}
