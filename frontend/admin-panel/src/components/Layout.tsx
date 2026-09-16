import { Link, NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { hasPerm, isPlatformSuperuser } from "../auth/permissions";
import { GROUP_LABELS } from "../types";

// Cada item requiere su propio permiso Django — un usuario sin ninguno de
// estos (ej. operadores/encargados_difusion/analistas_datos, que hoy no
// tienen NINGÚN permiso sobre Core, ver `users.group_permissions`) se queda
// sin nav acá abajo: para esos 3 grupos, Core es sólo su API de
// autenticación, no un panel con pantallas.
const NAV_ITEMS = [
  { to: "/usuarios", label: "Usuarios", perm: "users.view_user" },
  { to: "/equipos", label: "Equipos", perm: "teams.view_team" },
  { to: "/menu", label: "Menú", perm: "menu.view_menuopcion" },
  { to: "/horarios", label: "Horarios", perm: "business_hours.view_horarioatencion" },
  { to: "/mensajes", label: "Mensajes", perm: "bot_settings.view_botmessages" },
  { to: "/etiquetas", label: "Etiquetas", perm: "tags.view_etiqueta" },
  { to: "/canales", label: "Canales", perm: "channels.view_canal" },
];

// Sólo para el superusuario real de plataforma (`isPlatformSuperuser`) — a
// propósito una lista COMPLETAMENTE aparte de `NAV_ITEMS`, nunca mezcladas:
// ver el comentario de `isPlatformSuperuser` sobre por qué los permisos
// Django solos no alcanzan para separar "mi organización" de "toda la
// plataforma".
const PLATFORM_NAV_ITEMS = [
  { to: "/plataforma/organizaciones", label: "Organizaciones" },
  { to: "/plataforma/usuarios", label: "Usuarios" },
  { to: "/plataforma/tokens", label: "Tokens internos" },
  { to: "/plataforma/estadisticas", label: "Estadísticas" },
  { to: "/plataforma/manuales", label: "Manuales y API" },
];

export default function Layout() {
  const { me, logout } = useAuth();

  const navItems = isPlatformSuperuser(me)
    ? PLATFORM_NAV_ITEMS
    : NAV_ITEMS.filter((item) => hasPerm(me, item.perm));

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">Chat Multiagente</div>
        <nav>
          {navItems.map((item) => (
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
