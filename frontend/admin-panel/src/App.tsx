import { Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
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
            <Route path="/" element={<Navigate to="/menu" replace />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
