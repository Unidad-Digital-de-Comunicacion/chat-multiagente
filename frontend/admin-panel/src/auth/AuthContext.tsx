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

// El token sigue en `localStorage` (no cookies `httponly` — ver la
// discusión de arquitectura del 2026-09-20), así que un token robado por
// XSS seguiría sirviendo igual hasta que expire; esto no soluciona eso.
// Lo que sí mitiga: si un superusuario desactiva la cuenta o le saca un
// permiso mientras la pestaña sigue abierta, antes había que esperar hasta
// 30 minutos (la vida del `access`) a que el usuario recargue o haga un
// request que dispare un refresh — con esto, la pestaña se entera sola en
// como mucho este intervalo, sin esperar ninguna acción del usuario.
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
    // Sólo depende de si hay sesión o no (`Boolean(me)`), no de `me`
    // entero — no hay que reiniciar el timer cada vez que cambia el
    // perfil, sólo prenderlo/apagarlo al loguear/desloguear.
  }, [Boolean(me)]);

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
