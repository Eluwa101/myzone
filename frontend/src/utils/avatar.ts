import type { CSSProperties } from "react";

/** "Ada Obi" -> "AO", "Cher" -> "CH", "" -> "?" */
export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

/** A soft pastel circle whose colour is the same every time for the same
 * name, so a customer is recognisable at a glance. */
export function avatarStyle(name: string): CSSProperties {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  const hue = hash % 360;
  return { background: `hsl(${hue} 62% 87%)`, color: `hsl(${hue} 48% 26%)` };
}
