import { Link } from "react-router-dom";

/** Long text shown as a short preview. When it is clipped, a "View full"
 * link goes to the page that shows all of it - lists stay scannable and the
 * full text lives on its own page rather than stretching the card. */
export default function ClampText({
  text,
  to,
  lines = 3,
  maxChars = 240,
  label = "View full",
}: {
  text: string;
  to: string;
  lines?: number;
  /** below this length nothing is clipped, so short text never gets a button */
  maxChars?: number;
  label?: string;
}) {
  // line-clamp handles tall text; the length/newline check decides whether the
  // button appears at all, without measuring the DOM
  const clipped = text.length > maxChars || text.split("\n").length > lines;
  return (
    <>
      <p
        className="clamp-text"
        style={
          clipped
            ? { display: "-webkit-box", WebkitLineClamp: lines, WebkitBoxOrient: "vertical", overflow: "hidden", whiteSpace: "pre-wrap" }
            : { whiteSpace: "pre-wrap" }
        }
      >
        {text}
      </p>
      {clipped && (
        <Link to={to} className="small clamp-more">
          {label}
        </Link>
      )}
    </>
  );
}
