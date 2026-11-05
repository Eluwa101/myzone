import { Navigate, Route, Routes } from "react-router-dom";
import ProtectedLayout from "./components/ProtectedLayout";
import ServerWakingBanner from "./components/ServerWakingBanner";
import AskDataPage from "./pages/AskDataPage";
import ChatPage from "./pages/ChatPage";
import CustomerDetailPage from "./pages/CustomerDetailPage";
import CustomersPage from "./pages/CustomersPage";
import DashboardPage from "./pages/DashboardPage";
import DashboardInterestsPage from "./pages/DashboardInterestsPage";
import DashboardMonthlyPage from "./pages/DashboardMonthlyPage";
import DashboardTopCustomersPage from "./pages/DashboardTopCustomersPage";
import FormsPage from "./pages/FormsPage";
import LoginPage from "./pages/LoginPage";
import NotesPage from "./pages/NotesPage";
import PublicFormPage from "./pages/PublicFormPage";
import SegmentsPage from "./pages/SegmentsPage";
import SettingsPage from "./pages/SettingsPage";
import SignupPage from "./pages/SignupPage";

export default function App() {
  return (
    <>
      <ServerWakingBanner />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/f/:token" element={<PublicFormPage />} />

        <Route element={<ProtectedLayout />}>
          <Route path="/customers" element={<CustomersPage />} />
          <Route path="/customers/:id" element={<CustomerDetailPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/dashboard/top-customers" element={<DashboardTopCustomersPage />} />
          <Route path="/dashboard/monthly" element={<DashboardMonthlyPage />} />
          <Route path="/dashboard/interests" element={<DashboardInterestsPage />} />
          <Route path="/ask" element={<AskDataPage />} />
          <Route path="/notes" element={<NotesPage />} />
          <Route path="/forms" element={<FormsPage />} />
          <Route path="/segments" element={<SegmentsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/customers" replace />} />
      </Routes>
    </>
  );
}
