import { Navigate, Outlet } from "react-router";
import { useAuth } from "./useAuth.js";

export function RequireAdmin() {
  const { user, loading } = useAuth();

  if (loading) return <div className="page-loading">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin") return <Navigate to="/" replace />;

  return <Outlet />;
}
