import { Code2, LayoutTemplate, Type } from "lucide-react";
import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import HtmlPreviewFrame from "./HtmlPreviewFrame";
import RichTextEditor, { type RichTextEditorHandle } from "./RichTextEditor";

export interface EmailBodyEditorHandle {
  insertTextAtCursor: (text: string) => void;
}

type Mode = "visual" | "html";

/** Markup the visual editor can't represent - opening it there would
 * silently strip the layout, so a body like this starts in HTML mode. */
export function looksLikeCustomHtml(html: string): boolean {
  return /<(table|style|div|section|center|font)\b|<[a-z0-9]+[^>]*\sstyle\s*=\s*["'][^"']*(background|border|padding|width|font-family)/i.test(html);
}

/** The visual editor's idea of "empty" is <p><br></p>, not "". */
function isBlank(html: string): boolean {
  return !/<img/i.test(html) && html.replace(/<[^>]*>|&nbsp;/g, "").trim() === "";
}

const STARTER_LAYOUT = `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f7;padding:24px 0;">
  <tr>
    <td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:8px;overflow:hidden;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
        <tr>
          <td style="background:#4f46e5;padding:20px 24px;color:#ffffff;font-size:20px;font-weight:bold;">
            {{business.name}}
          </td>
        </tr>
        <tr>
          <td style="padding:24px;font-size:15px;line-height:1.6;">
            <p style="margin:0 0 12px;">Hi {{customer.first_name}},</p>
            <p style="margin:0 0 16px;">Thank you for shopping with us. Here are your recent purchases:</p>
            <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse:collapse;font-size:14px;">
              <tr style="background:#eef2ff;text-align:left;">
                <th>Date</th><th>Items</th><th align="right">Total</th>
              </tr>
              {{#each transactions limit 5}}
              <tr style="border-bottom:1px solid #e5e7eb;">
                <td>{{date}}</td><td>{{items}}</td><td align="right">{{currency}} {{amount}}</td>
              </tr>
              {{else}}
              <tr><td colspan="3">No purchases yet.</td></tr>
              {{/each}}
            </table>
            <p style="margin:16px 0 0;">Total spent with us: <b>{{stats.lifetime_spend}}</b></p>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 24px;background:#f9fafb;font-size:12px;color:#6b7280;">
            {{business.name}} · {{business.phone}} · {{business.address}}
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>`;

/** The email body field: a visual (rich-text) editor for everyday
 * messages, or an HTML source editor with a live preview for designed
 * templates - tables, inline CSS, images, colours. Merge tags insert at
 * the cursor in either mode.
 *
 * The mode is chosen once, when the editor mounts. A parent that swaps in
 * a different body wholesale (picking a template) should change this
 * component's `key`, so a designed template opens in HTML mode instead of
 * being flattened by the visual editor. */
const EmailBodyEditor = forwardRef<EmailBodyEditorHandle, { value: string; onChange: (html: string) => void; placeholder?: string }>(
  ({ value, onChange, placeholder }, ref) => {
    const [mode, setMode] = useState<Mode>(() => (looksLikeCustomHtml(value) ? "html" : "visual"));
    const [armedVisual, setArmedVisual] = useState(false);
    const quillRef = useRef<RichTextEditorHandle>(null);
    const sourceRef = useRef<HTMLTextAreaElement>(null);

    useImperativeHandle(ref, () => ({
      insertTextAtCursor(text: string) {
        if (mode === "visual") {
          quillRef.current?.insertTextAtCursor(text);
          return;
        }
        const el = sourceRef.current;
        const start = el?.selectionStart ?? value.length;
        const end = el?.selectionEnd ?? value.length;
        onChange(value.slice(0, start) + text + value.slice(end));
        requestAnimationFrame(() => {
          el?.focus();
          el?.setSelectionRange(start + text.length, start + text.length);
        });
      },
    }));

    function toVisual() {
      if (looksLikeCustomHtml(value) && !armedVisual) {
        setArmedVisual(true);
        return;
      }
      setArmedVisual(false);
      setMode("visual");
    }

    function toHtml() {
      setArmedVisual(false);
      if (isBlank(value) && value !== "") onChange("");
      setMode("html");
    }

    return (
      <div className="email-body-editor">
        <div className="editor-mode-tabs" role="tablist" aria-label="Editor mode">
          <button type="button" role="tab" aria-selected={mode === "visual"} className={mode === "visual" ? "active" : ""} onClick={toVisual}>
            <Type size={13} /> Visual
          </button>
          <button type="button" role="tab" aria-selected={mode === "html"} className={mode === "html" ? "active" : ""} onClick={toHtml}>
            <Code2 size={13} /> HTML
          </button>
        </div>
        {armedVisual && (
          <p className="small editor-mode-warning">
            The visual editor can't keep tables or custom styling - switching will simplify this design.{" "}
            <button type="button" className="btn-danger" onClick={toVisual}>
              Switch anyway
            </button>{" "}
            <button type="button" onClick={() => setArmedVisual(false)}>
              Stay in HTML
            </button>
          </p>
        )}

        {mode === "visual" ? (
          <RichTextEditor ref={quillRef} value={value} onChange={onChange} placeholder={placeholder} />
        ) : (
          <>
            <textarea
              ref={sourceRef}
              className="html-source"
              aria-label="Email HTML"
              rows={14}
              spellCheck={false}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              placeholder={'<table width="100%">\n  <tr>\n    <td style="padding:24px;">Hi {{customer.first_name}}, …</td>\n  </tr>\n</table>'}
            />
            <div className="row" style={{ marginTop: 6 }}>
              {isBlank(value) && (
                <button type="button" className="icon-btn btn-ghost small" onClick={() => onChange(STARTER_LAYOUT)}>
                  <LayoutTemplate size={14} /> Start from a sample layout
                </button>
              )}
              <span className="muted small">
                Use tables and inline <code>style="…"</code> for layout - email apps ignore most other CSS. Images need a public
                https:// link.
              </span>
            </div>
            <p className="muted small" style={{ margin: "10px 0 4px" }}>
              Live preview (merge tags are filled in when you press Preview or send)
            </p>
            <HtmlPreviewFrame html={value} title="Live HTML preview" />
          </>
        )}
      </div>
    );
  }
);

EmailBodyEditor.displayName = "EmailBodyEditor";

export default EmailBodyEditor;
