import { useEffect } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

/** Moving to a different page starts it at the top. Without this the browser
 * keeps the old page's scroll position, so a short page opened from the
 * bottom of a long one appears scrolled down. Going back (POP) is left to
 * the browser, so it can return you to where you were. */
export default function ScrollToTop() {
  const { pathname } = useLocation();
  const type = useNavigationType();

  useEffect(() => {
    if (type !== "POP") window.scrollTo(0, 0);
    // only a change of page counts - not tabs, filters or page numbers in the address
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  return null;
}
