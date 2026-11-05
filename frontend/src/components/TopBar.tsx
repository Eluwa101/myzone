import type { ReactNode } from "react";
import NotesBell from "./NotesBell";
import UserMenu from "./UserMenu";

export default function TopBar({ title, actions }: { title: string; actions?: ReactNode }) {
  return (
    <header className="top-bar">
      <h1>{title}</h1>
      <div className="top-bar-actions">
        {actions}
        <NotesBell />
        <UserMenu />
      </div>
    </header>
  );
}
