import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

const RUTA_CAMBIAR_CONTRASENA = "/cambiar-contrasena";

export default function ProtectedRoute() {
  const { me, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div className="page-loading">Cargando…</div>;

  if (!me) return <Navigate to="/login" replace />;

  // Después de que un Admin resetea la contraseña de alguien, esa persona
  // no puede usar el resto del panel hasta elegir la suya propia.
  if (me.must_change_password && location.pathname !== RUTA_CAMBIAR_CONTRASENA) {
    return <Navigate to={RUTA_CAMBIAR_CONTRASENA} replace />;
  }

  return <Outlet />;
}
