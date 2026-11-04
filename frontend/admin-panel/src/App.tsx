import { Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider, useAuth } from "./auth/AuthContext";
import { isPlatformSuperuser } from "./auth/permissions";
import Layout from "./components/Layout";
import ProtectedRoute from "./routes/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import ForgotUsernamePage from "./pages/ForgotUsernamePage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import ChangePasswordPage from "./pages/ChangePasswordPage";
import MyProfilePage from "./pages/MyProfilePage";
import UsersPage from "./pages/UsersPage";
import TeamsPage from "./pages/TeamsPage";
import MenuPage from "./pages/MenuPage";
import BusinessHoursPage from "./pages/BusinessHoursPage";
import BotMessagesPage from "./pages/BotMessagesPage";
import TagsPage from "./pages/TagsPage";
import ChannelsPage from "./pages/ChannelsPage";
import ConversationHistoryPage from "./pages/ConversationHistoryPage";
import PlatformOrganizationsPage from "./pages/PlatformOrganizationsPage";
import PlatformUsersPage from "./pages/PlatformUsersPage";
import PlatformTokensPage from "./pages/PlatformTokensPage";
import PlatformMetaAppPage from "./pages/PlatformMetaAppPage";
import PlatformStatsPage from "./pages/PlatformStatsPage";
import PlatformManualsPage from "./pages/PlatformManualsPage";
import PlatformIncidentsPage from "./pages/PlatformIncidentsPage";
import PlatformLogsPage from "./pages/PlatformLogsPage";

/** La organización usa "/menu" como landing porque casi todo el mundo tiene
 * permiso para verlo — el superusuario de plataforma no (no gestiona el
 * menú de ninguna organización en particular), así que lo mandamos a la
 * primera pantalla de su propia sección en cambio. */
function Home() {
  const { me } = useAuth();

  return <Navigate to={isPlatformSuperuser(me) ? "/plataforma/organizaciones" : "/menu"} replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/olvide-usuario" element={<ForgotUsernamePage />} />
        <Route path="/olvide-contrasena" element={<ForgotPasswordPage />} />
        <Route path="/restablecer-contrasena/:uid/:token" element={<ResetPasswordPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/cambiar-contrasena" element={<ChangePasswordPage />} />
          <Route element={<Layout />}>
            <Route path="/mi-perfil" element={<MyProfilePage />} />
            <Route path="/usuarios" element={<UsersPage />} />
            <Route path="/equipos" element={<TeamsPage />} />
            <Route path="/menu" element={<MenuPage />} />
            <Route path="/horarios" element={<BusinessHoursPage />} />
            <Route path="/mensajes" element={<BotMessagesPage />} />
            <Route path="/etiquetas" element={<TagsPage />} />
            <Route path="/canales" element={<ChannelsPage />} />
            <Route path="/historial-conversaciones" element={<ConversationHistoryPage />} />
            <Route path="/plataforma/organizaciones" element={<PlatformOrganizationsPage />} />
            <Route path="/plataforma/usuarios" element={<PlatformUsersPage />} />
            <Route path="/plataforma/tokens" element={<PlatformTokensPage />} />
            <Route path="/plataforma/meta-app" element={<PlatformMetaAppPage />} />
            <Route path="/plataforma/estadisticas" element={<PlatformStatsPage />} />
            <Route path="/plataforma/manuales" element={<PlatformManualsPage />} />
            <Route path="/plataforma/incidentes" element={<PlatformIncidentsPage />} />
            <Route path="/plataforma/logs" element={<PlatformLogsPage />} />
            <Route path="/plataforma/historial-conversaciones" element={<ConversationHistoryPage />} />
            <Route path="/" element={<Home />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
