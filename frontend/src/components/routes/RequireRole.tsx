import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";
import type { UserRole } from "@/types/auth";

/**
 * Nested inside <ProtectedRoute>. Restricts a route to specific roles
 * (e.g. allowed={["admin"]}) and redirects anyone else to /unauthorized.
 */
export function RequireRole({
  allowed,
  children,
}: {
  allowed: UserRole[];
  children: ReactNode;
}) {
  const { role, isLoading } = useAuth();
  const isBypass = import.meta.env.DEV && import.meta.env.VITE_DISABLE_LOGIN === 'true';

  if (isLoading && !isBypass) return null;

  if (!isBypass && (!role || !allowed.includes(role))) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
}
