import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

const NavigationHistoryContext = createContext(false);

/** Tracks how many in-app navigations deep the user is, so TopBar's back
 * button can call real browser-history back (landing on whatever screen
 * and scroll/filter state the user actually came from) instead of always
 * jumping to a hardcoded route - and still have a sensible fallback
 * destination for a page opened directly (deep link, refresh, new tab). */
export function NavigationHistoryProvider({ children }: { children: ReactNode }) {
  const location = useLocation();
  const navigationType = useNavigationType();
  const depthRef = useRef(0);
  const [canGoBack, setCanGoBack] = useState(false);

  useEffect(() => {
    if (navigationType === "PUSH") depthRef.current += 1;
    else if (navigationType === "POP") depthRef.current = Math.max(0, depthRef.current - 1);
    setCanGoBack(depthRef.current > 0);
    // navigationType can repeat (e.g. several PUSHes in a row) across
    // distinct navigations, so key the effect on location.key - the one
    // thing guaranteed to change on every single navigation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.key]);

  return <NavigationHistoryContext.Provider value={canGoBack}>{children}</NavigationHistoryContext.Provider>;
}

export function useCanGoBack(): boolean {
  return useContext(NavigationHistoryContext);
}
