import { Link, NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { GROUP_LABELS } from "../types";

const NAV_ITEMS = [
  { to: "/usuarios", label: "Usuarios" },
  { to: "/equipos", label: "Equipos" },
  { to: "/menu", label: "Menú" },
  { to: "/horarios", label: "Horarios" },
  { to: "/mensajes", label: "Mensajes" },
];

export default function Layout() {
  const { me, logout } = useAuth();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">Chat Multiagente</div>
        <nav>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => "nav-link" + (isActive ? " nav-link-active" : "")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <div>
            {me && (
              <span className="topbar-user">
                {me.avatar_thumbnail && <img src={me.avatar_thumbnail} alt="" className="avatar-thumb" />}
                {me.email}{" "}
                {me.groups.length === 0 ? (
                  <span className="badge">—</span>
                ) : (
                  me.groups.map((g) => (
                    <span key={g} className="badge">
                      {GROUP_LABELS[g] ?? g}
                    </span>
                  ))
                )}
              </span>
            )}
          </div>
          <div className="topbar-actions">
            <Link to="/mi-perfil" className="btn btn-ghost">
              Mi perfil
            </Link>
            <button className="btn btn-ghost" onClick={logout}>
              Cerrar sesión
            </button>
          </div>
        </header>
        <main className="page">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
