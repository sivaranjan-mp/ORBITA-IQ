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

  if (isLoading) return null;

  if (!role || !allowed.includes(role)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
}
