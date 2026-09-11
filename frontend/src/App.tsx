import { Navigate, Route, BrowserRouter, Routes } from "react-router-dom";
import NavSidebar from "./components/NavSidebar";
import PrototypeBanner from "./components/PrototypeBanner";
import QueuePage from "./pages/QueuePage";
import OrderDetailPage from "./pages/OrderDetailPage";
import ReportingPage from "./pages/ReportingPage";
import AlertsPage from "./pages/AlertsPage";
import AdminPage from "./pages/AdminPage";

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen flex-col bg-white text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
        <PrototypeBanner />
        <div className="flex flex-1 overflow-hidden">
          <NavSidebar />
          <main className="flex-1 overflow-auto">
            <Routes>
              <Route path="/" element={<Navigate to="/queue" replace />} />
              <Route path="/queue" element={<QueuePage />} />
              <Route path="/orders/:orderId" element={<OrderDetailPage />} />
              <Route path="/reporting" element={<ReportingPage />} />
              <Route path="/alerts" element={<AlertsPage />} />
              <Route path="/admin" element={<AdminPage />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}
