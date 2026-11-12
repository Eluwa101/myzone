import { ArrowLeft } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { LAST_UPDATED, LEGAL_DRAFT, PRIVACY_POLICY, TERMS_OF_SERVICE } from "../legal/content";

/** /privacy and /terms - public, no login needed, readable from the
 * signup screen before an account exists. */
export default function LegalPage({ doc }: { doc: "privacy" | "terms" }) {
  const content = doc === "privacy" ? PRIVACY_POLICY : TERMS_OF_SERVICE;
  const other = doc === "privacy" ? { to: "/terms", label: "Terms of Service" } : { to: "/privacy", label: "Privacy Policy" };

  useEffect(() => {
    document.title = `${content.title} - MyShop`;
    window.scrollTo(0, 0);
    return () => {
      document.title = "MyShop";
    };
  }, [content.title]);

  return (
    <div className="legal-page">
      <header className="legal-header">
        <Link to="/" className="legal-back">
          <ArrowLeft size={15} /> MyShop
        </Link>
        <Link to={other.to} className="small">
          {other.label}
        </Link>
      </header>

      <article>
        <h1>{content.title}</h1>
        <p className="muted small">Last updated {LAST_UPDATED}</p>
        {LEGAL_DRAFT && (
          <p className="legal-draft small">
            Draft - details in [square brackets] are still being finalised.
          </p>
        )}
        <p>{content.intro}</p>

        <nav className="legal-toc" aria-label="Contents">
          <p className="small">
            <b>Contents</b>
          </p>
          <ol>
            {content.sections.map((s) => (
              <li key={s.id}>
                <a href={`#${s.id}`}>{s.heading.replace(/^\d+\.\s*/, "")}</a>
              </li>
            ))}
          </ol>
        </nav>

        {content.sections.map((s) => (
          <section key={s.id} id={s.id}>
            <h2>{s.heading}</h2>
            {s.body.map((block, i) =>
              Array.isArray(block) ? (
                <ul key={i}>
                  {block.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p key={i}>{block}</p>
              )
            )}
          </section>
        ))}
      </article>

      <footer className="legal-footer small muted">
        <Link to="/developers">Developers</Link> · <Link to="/privacy">Privacy Policy</Link> · <Link to="/terms">Terms of Service</Link>
      </footer>
    </div>
  );
}
