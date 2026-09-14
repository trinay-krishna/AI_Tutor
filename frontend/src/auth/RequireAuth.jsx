import { Navigate, Outlet, useLocation } from "react-router";
import { useAuth } from "./useAuth.js";

export function RequireAuth() {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div className="page-loading">Loading…</div>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;

  return <Outlet />;
}
