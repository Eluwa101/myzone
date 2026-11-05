import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link } from "react-router-dom";

const CUSTOMER_LINK_PREFIX = "customer:";

// react-markdown sanitizes link hrefs to a safe-protocol allowlist by
// default (http/https/mailto/tel/relative) - a custom "customer:" scheme
// would otherwise be silently stripped, so it needs an explicit pass-through.
function urlTransform(url: string): string {
  return url.startsWith(CUSTOMER_LINK_PREFIX) ? url : defaultUrlTransform(url);
}

export default function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        urlTransform={urlTransform}
        components={{
          a: ({ href, children, ...props }) => {
            if (href?.startsWith(CUSTOMER_LINK_PREFIX)) {
              const customerId = href.slice(CUSTOMER_LINK_PREFIX.length);
              return <Link to={`/customers/${customerId}`}>{children}</Link>;
            }
            return (
              <a href={href} target="_blank" rel="noreferrer" {...props}>
                {children}
              </a>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
