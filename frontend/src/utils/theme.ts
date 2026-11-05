export type ThemePref = "light" | "dark" | "system";

const KEY = "mini_crm_theme";

export function getStoredTheme(): ThemePref {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    /* private mode / blocked storage - fall back to system */
  }
  return "system";
}

export function applyTheme(pref: ThemePref): void {
  const root = document.documentElement;
  if (pref === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", pref);
  try {
    localStorage.setItem(KEY, pref);
  } catch {
    /* non-fatal - theme just won't persist across sessions */
  }
}
