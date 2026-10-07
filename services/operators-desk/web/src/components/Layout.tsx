import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export default function Layout() {
  const { me, logout } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-left">
          <span className="app-brand">Operators Desk</span>
          <nav className="app-nav">
            <NavLink to="/bandeja/sin-asignar" className={({ isActive }) => (isActive ? "active" : "")}>
              Sin asignar
            </NavLink>
            <NavLink to="/bandeja/mias" className={({ isActive }) => (isActive ? "active" : "")}>
              Mis conversaciones
            </NavLink>
          </nav>
        </div>
        <div className="app-header-right">
          <span className="text-muted">{me?.email}</span>
          <NavLink to="/mi-perfil" className={({ isActive }) => (isActive ? "active" : "")}>
            Mi perfil
          </NavLink>
          <button type="button" className="btn btn-link" onClick={logout}>
            Salir
          </button>
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
