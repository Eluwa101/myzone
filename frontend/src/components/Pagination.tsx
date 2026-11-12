import { ChevronLeft, ChevronRight } from "lucide-react";

/** Page numbers to show: always the first and last, plus a couple either
 * side of the current one, with gaps ("…") in between. */
function pageList(current: number, last: number): (number | "gap")[] {
  const wanted = new Set([1, last, current - 1, current, current + 1]);
  if (current <= 3) [2, 3, 4].forEach((p) => wanted.add(p));
  if (current >= last - 2) [last - 1, last - 2, last - 3].forEach((p) => wanted.add(p));
  const pages = [...wanted].filter((p) => p >= 1 && p <= last).sort((a, b) => a - b);
  const out: (number | "gap")[] = [];
  pages.forEach((p, i) => {
    if (i > 0 && p - pages[i - 1] > 1) out.push("gap");
    out.push(p);
  });
  return out;
}

export default function Pagination({
  page,
  pageSize,
  total,
  onChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}) {
  const last = Math.max(1, Math.ceil(total / pageSize));
  if (total === 0) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);

  return (
    <nav className="pagination" aria-label="Pages">
      <span className="muted small">
        Showing {from.toLocaleString()}–{to.toLocaleString()} of {total.toLocaleString()}
      </span>
      {last > 1 && (
        <div className="pagination-pages">
          <button type="button" onClick={() => onChange(page - 1)} disabled={page <= 1} aria-label="Previous page">
            <ChevronLeft size={16} />
          </button>
          {pageList(page, last).map((p, i) =>
            p === "gap" ? (
              <span key={`gap-${i}`} className="pagination-gap" aria-hidden="true">
                …
              </span>
            ) : (
              <button
                key={p}
                type="button"
                className={p === page ? "pagination-current" : undefined}
                aria-current={p === page ? "page" : undefined}
                aria-label={`Page ${p}`}
                onClick={() => onChange(p)}
              >
                {p}
              </button>
            )
          )}
          <button type="button" onClick={() => onChange(page + 1)} disabled={page >= last} aria-label="Next page">
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </nav>
  );
}
