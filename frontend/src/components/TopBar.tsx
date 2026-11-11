import { ChevronLeft } from "lucide-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useCanGoBack } from "../context/NavigationHistoryContext";
import HeaderMenu from "./HeaderMenu";
import NotificationBell from "./NotificationBell";
import SyncStatusIndicator from "./SyncStatusIndicator";
import UserMenu from "./UserMenu";

export default function TopBar({ title, actions, backTo }: { title: string; actions?: ReactNode; backTo?: string }) {
  const navigate = useNavigate();
  const canGoBack = useCanGoBack();
  // Real history-back whenever there's somewhere to go back to (lands on
  // whatever screen/filters/scroll the user actually came from) - backTo
  // is only a fallback for a page opened directly (deep link, refresh).
  const showBack = canGoBack || !!backTo;
  function goBack() {
    if (canGoBack) navigate(-1);
    else if (backTo) navigate(backTo);
  }
  return (
    <header className="top-bar">
      <div className="top-bar-title">
        {showBack && (
          <button type="button" className="icon-btn btn-ghost" aria-label="Back" onClick={goBack}>
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
