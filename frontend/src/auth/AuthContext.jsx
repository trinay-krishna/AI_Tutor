import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../api.js";
import { AuthContext } from "./auth-context.js";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    api
      .get("/auth/me")
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch((err) => {
        if (cancelled) return;
        if (!(err instanceof ApiError && err.status === 401)) throw err;
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email, password) => {
    const me = await api.post("/auth/login", { email, password });
    setUser(me);
    return me;
  }, []);

  const register = useCallback(async (email, password) => {
    const me = await api.post("/auth/register", { email, password });
    setUser(me);
    return me;
  }, []);

  const logout = useCallback(async () => {
    await api.post("/auth/logout");
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
