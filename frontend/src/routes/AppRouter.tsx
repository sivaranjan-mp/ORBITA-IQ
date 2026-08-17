import { Navigate, Route, Routes } from "react-router-dom";

import { MissionControlLayout } from "@/components/layout/MissionControlLayout";
import { ProtectedRoute } from "@/components/routes/ProtectedRoute";
import { AlertsPage } from "@/pages/AlertsPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { ForgotPasswordPage } from "@/pages/ForgotPasswordPage";
import { LoginPage } from "@/pages/LoginPage";
import { MySatellitesPage } from "@/pages/MySatellitesPage";
import { OrbitViewerPage } from "@/pages/OrbitViewerPage";
import { ResetPasswordPage } from "@/pages/ResetPasswordPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { UnauthorizedPage } from "@/pages/UnauthorizedPage";

export function AppRouter() {
  return (
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
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/orbit-viewer" element={<OrbitViewerPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>

      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

