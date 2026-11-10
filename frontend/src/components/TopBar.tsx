import { ChevronLeft } from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import HeaderMenu from "./HeaderMenu";
import NotificationBell from "./NotificationBell";
import SyncStatusIndicator from "./SyncStatusIndicator";
import UserMenu from "./UserMenu";

export default function TopBar({ title, actions, backTo }: { title: string; actions?: ReactNode; backTo?: string }) {
  const navigate = useNavigate();
  return (
    <header className="top-bar">
      <div className="top-bar-title">
        {backTo && (
          <button type="button" className="icon-btn btn-ghost" aria-label="Back" onClick={() => navigate(backTo)}>
            <ChevronLeft size={20} />
          </button>
        )}
        <h1>{title}</h1>
      </div>
      <div className="top-bar-actions">
        {actions}
        <SyncStatusIndicator />
        <NotificationBell />
        <HeaderMenu />
        <UserMenu />
      </div>
    </header>
  );
}
