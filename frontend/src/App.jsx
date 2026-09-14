import { Navigate, Route, Routes } from "react-router";
import { RequireAdmin } from "./auth/RequireAdmin.jsx";
import { RequireAuth } from "./auth/RequireAuth.jsx";
import NavBar from "./components/NavBar.jsx";
import AdminTechnologies from "./pages/admin/AdminTechnologies.jsx";
import AdminTechnologyDetail from "./pages/admin/AdminTechnologyDetail.jsx";
import Chat from "./pages/Chat.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import Technologies from "./pages/Technologies.jsx";
import "./App.css";

export default function App() {
  return (
    <>
      <NavBar />
      <main className="app-main">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          <Route element={<RequireAuth />}>
            <Route path="/" element={<Technologies />} />
            <Route path="/learn/:slug" element={<Chat />} />

            <Route element={<RequireAdmin />}>
              <Route path="/admin" element={<AdminTechnologies />} />
              <Route path="/admin/:slug" element={<AdminTechnologyDetail />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </>
  );
}
