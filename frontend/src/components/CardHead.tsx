import type { ReactNode } from "react";
import CardMenu, { type MenuItem } from "./CardMenu";

export type CardTone = "blue" | "teal" | "amber" | "rose" | "violet" | "slate";

/** The top of a card: a pastel icon tile, a title (with an optional small
 * line under it), any badges, and the "⋯" menu for the card's actions. */
export default function CardHead({
  icon,
  tone = "blue",
  title,
  subtitle,
  badges,
  items = [],
}: {
  icon: ReactNode;
  tone?: CardTone;
  title: ReactNode;
  subtitle?: ReactNode;
  badges?: ReactNode;
  items?: MenuItem[];
}) {
  return (
    <div className="card-head">
      <span className={`card-icon tone-${tone}`} aria-hidden="true">
        {icon}
      </span>
      <div className="card-head-text">
        <div className="card-title">{title}</div>
        {subtitle && <div className="card-sub">{subtitle}</div>}
      </div>
      {badges}
      <CardMenu items={items} />
    </div>
  );
}
