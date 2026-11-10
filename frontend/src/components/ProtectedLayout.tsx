import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import BottomNav from "./BottomNav";
import QuickCreateFab from "./QuickCreateFab";
import Spinner from "./Spinner";

const QUICK_CREATE_HIDDEN_ON = ["/onboarding"];

export default function ProtectedLayout() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <Spinner label="Checking your session…" />;
  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="app-shell">
      <main className="app-content">
        <Outlet />
      </main>
      {!QUICK_CREATE_HIDDEN_ON.includes(location.pathname) && <QuickCreateFab />}
      <BottomNav />
    </div>
  );
}
