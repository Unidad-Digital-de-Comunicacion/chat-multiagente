import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api } from "../api/client";
import { hasSession, setTokens } from "../api/client";
import type { Me } from "../types";

interface AuthState {
  me: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<Me>;
  logout: () => void;
  refreshMe: () => Promise<Me | null>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

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

  async function login(email: string, password: string): Promise<Me> {
    const data = await api.post<{ access: string; refresh: string }>("/api/auth/login/", { email, password });
    setTokens(data);
    // `setMe` de acá adentro es async (no se ve reflejado en el `me` del contexto hasta el
    // próximo render) — devolvemos el valor recién cargado para que quien llama a `login`
    // (ej. `LoginPage`, para decidir a dónde navegar) no dependa de un closure viejo.
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
