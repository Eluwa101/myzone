import { useRef, useState } from "react";

const MIN_HEIGHT = 80;
const MAX_HEIGHT = 560;

/** Renders email HTML the way an inbox would: on its own white page, cut
 * off from the app. The iframe is sandboxed without allow-scripts, so
 * nothing in the markup can run, and a template's own <style> block can't
 * leak into (or be restyled by) the app around it. */
export default function HtmlPreviewFrame({ html, title = "Email preview" }: { html: string; title?: string }) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(MIN_HEIGHT);

  const srcDoc =
    '<!doctype html><html><head><meta charset="utf-8"><base target="_blank">' +
    "<style>body{margin:12px;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.5;color:#111;background:#fff;word-wrap:break-word}img{max-width:100%}</style>" +
    `</head><body>${html}</body></html>`;

  function fitToContent() {
    const doc = frameRef.current?.contentDocument;
    if (doc) setHeight(Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, doc.documentElement.scrollHeight)));
  }

  return (
    <iframe
      ref={frameRef}
      className="html-preview-frame"
      title={title}
      sandbox="allow-same-origin"
      srcDoc={srcDoc}
      onLoad={fitToContent}
      style={{ height }}
    />
  );
}
