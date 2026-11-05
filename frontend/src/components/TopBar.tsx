import type { ReactNode } from "react";
import UserMenu from "./UserMenu";

export default function TopBar({ title, actions }: { title: string; actions?: ReactNode }) {
  return (
    <header className="top-bar">
      <h1>{title}</h1>
      <div className="top-bar-actions">
        {actions}
        <UserMenu />
      </div>
    </header>
  );
}
