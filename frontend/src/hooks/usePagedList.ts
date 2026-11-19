import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { errorMessage } from "../api/errorMessage";
import type { Paged } from "../api/client";

export interface PagedQuery {
  search: string;
  page: number;
  pageSize: number;
}

interface Options<T> {
  fetcher: (query: PagedQuery) => Promise<Paged<T>>;
  pageSize?: number;
  /** anything else the list depends on (a filter tab, say). When it changes the list goes back to page 1. */
  filterKey?: string;
}

/** The one list pattern: server-side search + pages, both kept in the URL so
 * opening an item and pressing back returns to the same page of the same
 * search. Typing is debounced; page changes and filter changes are not. */
export function usePagedList<T>({ fetcher, pageSize = 20, filterKey = "" }: Options<T>) {
  const [searchParams, setSearchParams] = useSearchParams();
  const page = Math.max(1, Number(searchParams.get("page")) || 1);
  const urlSearch = searchParams.get("q") ?? "";

  // the input is edited locally and pushed to the URL after a pause
  const [input, setInput] = useState(urlSearch);
  const [items, setItems] = useState<T[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const setParams = useCallback(
    (mutate: (params: URLSearchParams) => void, replace: boolean) => {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current);
          mutate(next);
          return next;
        },
        { replace }
      );
    },
    [setSearchParams]
  );

  const goToPage = useCallback(
    (next: number) => {
      setParams((p) => (next <= 1 ? p.delete("page") : p.set("page", String(next))), false);
      window.scrollTo({ top: 0 });
    },
    [setParams]
  );

  // push the typed text into the URL (and back to page 1) after a pause
  useEffect(() => {
    if (input === urlSearch) return;
    const handle = setTimeout(() => {
      setParams((p) => {
        if (input) p.set("q", input);
        else p.delete("q");
        p.delete("page");
      }, true);
    }, 250);
    return () => clearTimeout(handle);
  }, [input, urlSearch, setParams]);

  // a filter changing (not the first render) goes back to page 1
  const lastFilterKey = useRef(filterKey);
  useEffect(() => {
    if (lastFilterKey.current === filterKey) return;
    lastFilterKey.current = filterKey;
    if (page !== 1) setParams((p) => p.delete("page"), true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterKey]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetcherRef
      .current({ search: urlSearch, page, pageSize })
      .then((res) => {
        if (cancelled) return;
        // a page past the end (items were deleted, or an old link) falls back to the last page
        const last = Math.max(1, Math.ceil(res.total / pageSize));
        if (page > last) {
          setParams((p) => (last <= 1 ? p.delete("page") : p.set("page", String(last))), true);
          return;
        }
        setItems(res.items);
        setTotal(res.total);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(errorMessage(err));
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [urlSearch, page, pageSize, filterKey, tick, setParams]);

  return {
    items,
    total,
    loading,
    error,
    page,
    pageSize,
    goToPage,
    search: input,
    setSearch: setInput,
    searching: urlSearch !== "",
    reload: () => setTick((t) => t + 1),
  };
}
