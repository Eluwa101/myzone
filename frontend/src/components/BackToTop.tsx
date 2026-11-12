import { ArrowUp } from "lucide-react";
import { useEffect, useState } from "react";

/** A small round button that fades in once you've scrolled about a screen
 * down, and takes you back to the top. Tucked into a bottom corner, clear of
 * the + button, and see-through enough not to hide what's behind it.
 * `plain` is for pages without the navigation bar (privacy, terms, ...). */
export default function BackToTop({ plain = false }: { plain?: boolean }) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    let frame = 0;
    function update() {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => setShow(window.scrollY > Math.max(500, window.innerHeight * 0.8)));
    }
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", update);
    };
  }, []);

  function toTop() {
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: calm ? "auto" : "smooth" });
  }

  return (
    <button
      type="button"
      className={`back-to-top${show ? " visible" : ""}${plain ? " plain" : ""}`}
      aria-label="Back to top"
      title="Back to top"
      tabIndex={show ? 0 : -1}
      aria-hidden={!show}
      onClick={toTop}
    >
      <ArrowUp size={16} />
    </button>
  );
}
