import { useEffect, useState } from "react";
import { errorMessage } from "../api/errorMessage";
import type { Paged } from "../api/client";

/** Paging for a list nested inside another page (a form's submissions, a
 * webhook's deliveries) where the URL's `page` already belongs to the outer
 * list - so the page is plain component state here. `key` identifies which
 * list this is; a different key starts again from page 1. `fetcher` should be
 * stable for a given key (it's called whenever the page or key changes). */
export function useLocalPagedList<T>(fetcher: (page: number, pageSize: number) => Promise<Paged<T>>, pageSize: number, key: string) {
  const [pageState, setPageState] = useState({ key, page: 1 });
  const page = pageState.key === key ? pageState.page : 1;
  const setPage = (next: number) => setPageState({ key, page: next });

  const [result, setResult] = useState<{ key: string; page: number; items: T[]; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetcher(page, pageSize)
      .then((res) => {
        if (cancelled) return;
        const last = Math.max(1, Math.ceil(res.total / pageSize));
        if (page > last) setPageState({ key, page: last });
        else setResult({ key, page, items: res.items, total: res.total });
      })
      .catch((err) => {
        if (!cancelled) setError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, key]);

  // never show another list's (or another page's) rows under this one
  const current = result && result.key === key && result.page === page ? result : null;
  return { items: current ? current.items : null, total: current ? current.total : 0, page, setPage, error };
}
