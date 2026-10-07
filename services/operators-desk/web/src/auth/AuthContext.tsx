import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api, hasSession, setTokens } from "../api/client";
import type { Me } from "../types";

interface AuthState {
  me: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<Me>;
  logout: () => void;
  refreshMe: () => Promise<Me | null>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

// Mismo criterio que frontend/admin-panel/src/auth/AuthContext.tsx: revalidar
// el perfil cada tanto para enterarnos si alguien nos sacó el usuario o nos
// resetió permisos sin esperar a que el JWT venza (30 min) o a que el
// operador haga un request que dispare un refresh.
const INTERVALO_REVALIDACION_MS = 5 * 60 * 1000;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadMe(): Promise<Me | null> {
    try {
      const data = await api.get<Me>("/api/core/users/me/");
      setMe(data);

      return data;
    } catch {
      setMe(null);

      return null;
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

  useEffect(() => {
    if (!me) return;

    const id = setInterval(loadMe, INTERVALO_REVALIDACION_MS);

    return () => clearInterval(id);
  }, [Boolean(me)]);

  async function login(email: string, password: string): Promise<Me> {
    const data = await api.post<{ access: string; refresh: string }>("/api/auth/login/", { email, password });
    setTokens(data);
    const nuevoMe = await loadMe();

    if (!nuevoMe) throw new Error("No se pudo cargar el perfil después de iniciar sesión.");

    return nuevoMe;
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
