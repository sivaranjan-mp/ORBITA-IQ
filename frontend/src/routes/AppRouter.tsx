import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { MissionControlLayout } from "@/components/layout/MissionControlLayout";
import { ProtectedRoute } from "@/components/routes/ProtectedRoute";
import { AiAssistantPage } from "@/pages/AiAssistantPage";
import { AlertsPage } from "@/pages/AlertsPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { ForgotPasswordPage } from "@/pages/ForgotPasswordPage";
import { LoginPage } from "@/pages/LoginPage";
import { MySatellitesPage } from "@/pages/MySatellitesPage";
import { AllSatellitesPage } from "@/pages/AllSatellitesPage";
import { OrbitViewerPage } from "@/pages/OrbitViewerPage";
import { ResetPasswordPage } from "@/pages/ResetPasswordPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { UnauthorizedPage } from "@/pages/UnauthorizedPage";

const ROUTE_TITLES: Record<string, string> = {
  "/login": "Orbita-IQ — Sign In",
  "/forgot-password": "Orbita-IQ — Forgot Password",
  "/reset-password": "Orbita-IQ — Reset Password",
  "/unauthorized": "Orbita-IQ — Unauthorized",
  "/dashboard": "Orbita-IQ — Dashboard",
  "/satellites": "Orbita-IQ — My Satellites",
  "/all-satellites": "Orbita-IQ — All Satellites",
  "/ai-assistant": "Orbita-IQ — AI Assistant",
  "/alerts": "Orbita-IQ — Alerts",
  "/orbit-viewer": "Orbita-IQ — Orbit Viewer",
  "/settings": "Orbita-IQ — Settings",
};

function PageTitleUpdater() {
  const location = useLocation();

  useEffect(() => {
    const title = ROUTE_TITLES[location.pathname] || "Orbita-IQ — Mission Control";
    document.title = title;
  }, [location.pathname]);

  return null;
}

export function AppRouter() {
  return (
    <>
      <PageTitleUpdater />
      <Routes>
      {/* Public */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/unauthorized" element={<UnauthorizedPage />} />

      {/* Protected — Mission Control shell, any authenticated role */}
      <Route
        element={
          <ProtectedRoute>
            <MissionControlLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/satellites" element={<MySatellitesPage />} />
        <Route path="/all-satellites" element={<AllSatellitesPage />} />
        <Route path="/ai-assistant" element={<AiAssistantPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/orbit-viewer" element={<OrbitViewerPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
    </>
  );
}

