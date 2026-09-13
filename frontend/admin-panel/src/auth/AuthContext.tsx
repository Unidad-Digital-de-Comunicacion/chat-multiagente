import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api } from "../api/client";
import { hasSession, setTokens } from "../api/client";
import type { Me } from "../types";

interface AuthState {
  me: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadMe() {
    try {
      const data = await api.get<Me>("/api/core/users/me/");
      setMe(data);
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (hasSession()) {
      loadMe();
    } else {
      setLoading(false);
    }
  }, []);

  async function login(email: string, password: string) {
    const data = await api.post<{ access: string; refresh: string }>("/api/auth/login/", { email, password });
    setTokens(data);
    await loadMe();
  }

  function logout() {
    setTokens(null);
    setMe(null);
  }

  return (
    <AuthContext.Provider value={{ me, loading, login, logout, refreshMe: loadMe }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
