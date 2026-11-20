/** Fill-in-the-blanks like [discount] - same rule as the backend's
 * find_placeholders, checked live so the warning shows while typing. */
export function findPlaceholders(...texts: string[]): string[] {
  const decoder = document.createElement("textarea");
  const found: string[] = [];
  for (const text of texts) {
    decoder.innerHTML = text;
    for (const m of decoder.value.matchAll(/\[([A-Za-z][A-Za-z0-9 _\-/'&.]{0,40})\]/g)) {
      if (!found.includes(m[0])) found.push(m[0]);
    }
  }
  return found;
}

/** True when an HTML body has no visible text - an empty editor still holds "<p></p>". */
export function isBlankHtml(html: string): boolean {
  return html.replace(/<[^>]*>|&nbsp;/g, "").trim().length === 0;
}

/** Markup the visual editor can't represent - opening it there would
 * silently strip the layout, so a body like this starts in HTML mode. */
export function looksLikeCustomHtml(html: string): boolean {
  return /<(table|style|div|section|center|font)\b|<[a-z0-9]+[^>]*\sstyle\s*=\s*["'][^"']*(background|border|padding|width|font-family)/i.test(html);
}
