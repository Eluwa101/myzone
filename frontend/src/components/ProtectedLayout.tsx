import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import AdminSessionBanner from "./AdminSessionBanner";
import BackToTop from "./BackToTop";
import BottomNav from "./BottomNav";
import ClosureBanner from "./ClosureBanner";
import QuickCreateFab from "./QuickCreateFab";
import Spinner from "./Spinner";

const QUICK_CREATE_HIDDEN_ON = ["/onboarding"];

// pages that are collections of cards use the full desktop width; forms,
// profiles and the chat stay a comfortable reading width
const WIDE_ROUTES = ["/customers", "/dashboard", "/notes", "/messages/templates", "/forms", "/segments", "/webhooks", "/orders", "/scan", "/data"];

export default function ProtectedLayout() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <Spinner label="Checking your session…" />;
  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="app-shell">
      <main className={`app-content${WIDE_ROUTES.includes(location.pathname.replace(/\/$/, "")) ? " wide" : ""}`}>
        <AdminSessionBanner />
        <ClosureBanner />
        <Outlet />
      </main>
      {!QUICK_CREATE_HIDDEN_ON.includes(location.pathname) && <QuickCreateFab />}
      <BackToTop />
      <BottomNav />
    </div>
  );
}
