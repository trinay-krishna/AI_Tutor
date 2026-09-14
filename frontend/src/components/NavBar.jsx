import { Link, useNavigate } from "react-router";
import { useAuth } from "../auth/useAuth.js";

export default function NavBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <nav className="navbar">
      <Link to="/" className="navbar-brand">
        AI Tutor
      </Link>
      <div className="navbar-links">
        {user?.role === "admin" && <Link to="/admin">Admin</Link>}
        {user && <span className="navbar-email">{user.email}</span>}
        {user && (
          <button type="button" onClick={handleLogout}>
            Log out
          </button>
        )}
      </div>
    </nav>
  );
}
