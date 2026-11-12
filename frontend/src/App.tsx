import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import ProtectedLayout from "./components/ProtectedLayout";
import ServerWakingBanner from "./components/ServerWakingBanner";
import Spinner from "./components/Spinner";

// Routed pages are lazy-loaded so a first visit (almost always /login) only
// downloads/parses the code it actually needs, instead of one bundle for
// the whole app - this is the single biggest lever on initial load time.
const AskDataPage = lazy(() => import("./pages/AskDataPage"));
const CheckEmailPage = lazy(() => import("./pages/CheckEmailPage"));
const ChatPage = lazy(() => import("./pages/ChatPage"));
const CustomerDetailPage = lazy(() => import("./pages/CustomerDetailPage"));
const CustomersPage = lazy(() => import("./pages/CustomersPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const DashboardInterestsPage = lazy(() => import("./pages/DashboardInterestsPage"));
const DashboardMonthlyPage = lazy(() => import("./pages/DashboardMonthlyPage"));
const DashboardTopCustomersPage = lazy(() => import("./pages/DashboardTopCustomersPage"));
const DataPage = lazy(() => import("./pages/DataPage"));
const DevelopersPage = lazy(() => import("./pages/DevelopersPage"));
const EmailTemplatesPage = lazy(() => import("./pages/EmailTemplatesPage"));
const ForgotPasswordPage = lazy(() => import("./pages/ForgotPasswordPage"));
const FormsPage = lazy(() => import("./pages/FormsPage"));
const LegalPage = lazy(() => import("./pages/LegalPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const MessageComposePage = lazy(() => import("./pages/MessageComposePage"));
const MessagesPage = lazy(() => import("./pages/MessagesPage"));
const NotesPage = lazy(() => import("./pages/NotesPage"));
const OnboardingPage = lazy(() => import("./pages/OnboardingPage"));
const OrdersPage = lazy(() => import("./pages/OrdersPage"));
const PublicFormPage = lazy(() => import("./pages/PublicFormPage"));
const ResetPasswordPage = lazy(() => import("./pages/ResetPasswordPage"));
const ScanPage = lazy(() => import("./pages/ScanPage"));
const SegmentsPage = lazy(() => import("./pages/SegmentsPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const SignupPage = lazy(() => import("./pages/SignupPage"));
const UnsubscribePage = lazy(() => import("./pages/UnsubscribePage"));
const VerifyEmailPage = lazy(() => import("./pages/VerifyEmailPage"));
const WebhooksPage = lazy(() => import("./pages/WebhooksPage"));

export default function App() {
  return (
    <>
      <ServerWakingBanner />
      <Suspense fallback={<Spinner label="Loading…" />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/check-email" element={<CheckEmailPage />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/f/:token" element={<PublicFormPage />} />
          <Route path="/unsubscribe/:token" element={<UnsubscribePage />} />
          <Route path="/privacy" element={<LegalPage doc="privacy" />} />
          <Route path="/terms" element={<LegalPage doc="terms" />} />
          <Route path="/developers" element={<DevelopersPage />} />

          <Route element={<ProtectedLayout />}>
            <Route path="/onboarding" element={<OnboardingPage />} />
            <Route path="/customers" element={<CustomersPage />} />
            <Route path="/customers/:id" element={<CustomerDetailPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/dashboard/top-customers" element={<DashboardTopCustomersPage />} />
            <Route path="/dashboard/monthly" element={<DashboardMonthlyPage />} />
            <Route path="/dashboard/interests" element={<DashboardInterestsPage />} />
            <Route path="/ask" element={<AskDataPage />} />
            <Route path="/notes" element={<NotesPage />} />
            <Route path="/messages" element={<MessagesPage />} />
            <Route path="/messages/compose" element={<MessageComposePage />} />
            <Route path="/messages/templates" element={<EmailTemplatesPage />} />
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/forms" element={<FormsPage />} />
            <Route path="/segments" element={<SegmentsPage />} />
            <Route path="/scan" element={<ScanPage />} />
            <Route path="/webhooks" element={<WebhooksPage />} />
            <Route path="/data" element={<DataPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/customers" replace />} />
        </Routes>
      </Suspense>
    </>
  );
}
