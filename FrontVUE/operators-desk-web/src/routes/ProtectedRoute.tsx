import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

const RUTA_CAMBIAR_CONTRASENA = "/cambiar-contrasena";

export default function ProtectedRoute() {
  const { me, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div className="page-loading">Cargando…</div>;

  if (!me) return <Navigate to="/login" replace />;

  // Igual que en el Admin Panel: si un admin le reseteó la contraseña a
  // este operador, no puede usar el resto de la bandeja hasta elegir una
  // nueva (§1 del contrato de API: must_change_password).
  if (me.must_change_password && location.pathname !== RUTA_CAMBIAR_CONTRASENA) {
    return <Navigate to={RUTA_CAMBIAR_CONTRASENA} replace />;
  }

  return <Outlet />;
}
