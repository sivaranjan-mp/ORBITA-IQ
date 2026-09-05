import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";

/**
 * Gate for any route that requires a signed-in user. Unauthenticated
 * visitors are redirected to /login, with the originally requested
 * location preserved so LoginForm can send them back afterwards.
 */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  const isBypass = import.meta.env.DEV && import.meta.env.VITE_DISABLE_LOGIN === 'true';

  if (isLoading && !isBypass) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!isAuthenticated && !isBypass) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
