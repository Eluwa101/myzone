// One place for everything wa.me: phone cleanup, link building, and turning an
// HTML email draft into the plain text WhatsApp wants. Previously the settings
// page, segments page and email composer each had their own slightly different
// copy of this, and only some of them validated anything.

export type PhoneResult = { ok: true; digits: string } | { ok: false; reason: string };

const MIN_DIGITS = 8;
const MAX_DIGITS = 15; // E.164 maximum

// wa.me puts the whole message in the URL, and some browsers / WhatsApp
// clients silently drop or truncate links past roughly 2000 characters.
export const MAX_ENCODED_MESSAGE_LENGTH = 1800;

/** Turn whatever a person typed into the digits wa.me needs, or say why not.
 *
 *  `defaultCountryCode` (digits only, e.g. "234") completes numbers saved in
 *  local format with a leading trunk 0 ("0801 234 5678"). Numbers with no `+`
 *  and no leading 0 are assumed to already include their country code. */
export function normalizePhone(raw: string | null | undefined, defaultCountryCode?: string | null): PhoneResult {
  const text = (raw ?? "").trim();
  if (!text) return { ok: false, reason: "No phone number" };
  if (/[a-z]/i.test(text)) return { ok: false, reason: "Contains letters" };

  // "+234 (0) 801 234 5678" - the (0) is the local trunk prefix people write
  // out of habit; it must not be dialled after a country code
  const withoutTrunk = text.replace(/\(0\)/g, "");
  let digits = withoutTrunk.replace(/\D/g, "");
  const international = withoutTrunk.startsWith("+") || digits.startsWith("00");

  if (digits.startsWith("00")) digits = digits.slice(2);
  else if (!international && digits.startsWith("0")) {
    const cc = (defaultCountryCode ?? "").replace(/\D/g, "");
    if (!cc) return { ok: false, reason: "Local number - add the country code (or set a default country code in Settings)" };
    digits = cc + digits.slice(1);
  }

  if (digits.length < MIN_DIGITS) return { ok: false, reason: "Too short" };
  if (digits.length > MAX_DIGITS) return { ok: false, reason: "Too long" };
  if (digits.startsWith("0")) return { ok: false, reason: "Starts with 0 - add the country code" };
  return { ok: true, digits };
}

export interface WaLink {
  url: string;
  /** the message is too long to reliably fit in a chat link */
  tooLong: boolean;
}

export function buildWaLink(digits: string, message: string): WaLink {
  const encoded = encodeURIComponent(message);
  return { url: `https://wa.me/${digits}?text=${encoded}`, tooLong: encoded.length > MAX_ENCODED_MESSAGE_LENGTH };
}

/** A chat link for a raw saved phone number, or null if it isn't usable. */
export function waLinkFor(phone: string | null | undefined, message: string, defaultCountryCode?: string | null): WaLink | null {
  const result = normalizePhone(phone, defaultCountryCode);
  return result.ok ? buildWaLink(result.digits, message) : null;
}

/** Plain-text version of an HTML message body. Keeps the things that matter in
 *  a chat: line breaks, list bullets, and link URLs (which `textContent` alone
 *  would silently drop, leaving "Shop now" with nowhere to go). */
export function htmlToPlainText(html: string): string {
  const doc = new DOMParser().parseFromString(html, "text/html");
  doc.querySelectorAll("script, style, head, noscript").forEach((node) => node.remove());
  doc.querySelectorAll("br").forEach((node) => node.replaceWith(doc.createTextNode("\n")));
  doc.querySelectorAll("a[href]").forEach((node) => {
    const href = (node.getAttribute("href") ?? "").trim();
    const label = (node.textContent ?? "").trim();
    if (!/^https?:\/\//i.test(href)) return; // skip mailto:, tel:, javascript:, relative links
    node.textContent = !label || label === href || label === href.replace(/^https?:\/\//i, "") ? href : `${label} (${href})`;
  });
  doc.querySelectorAll("li").forEach((node) => node.prepend(doc.createTextNode("• ")));
  doc.querySelectorAll("p, div, li, tr, h1, h2, h3, h4, blockquote").forEach((node) => node.append(doc.createTextNode("\n")));
  return (doc.body.textContent ?? "").replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
}
