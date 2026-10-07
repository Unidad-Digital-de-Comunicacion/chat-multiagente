import { Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import Layout from "./components/Layout";
import ProtectedRoute from "./routes/ProtectedRoute";
import ChangePasswordPage from "./pages/ChangePasswordPage";
import ConversationPage from "./pages/ConversationPage";
import InboxPage from "./pages/InboxPage";
import LoginPage from "./pages/LoginPage";
import MyProfilePage from "./pages/MyProfilePage";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/cambiar-contrasena" element={<ChangePasswordPage />} />
          <Route element={<Layout />}>
            <Route path="/bandeja/sin-asignar" element={<InboxPage bandeja="sin_asignar" />} />
            <Route path="/bandeja/mias" element={<InboxPage bandeja="mias" />} />
            <Route path="/conversaciones/:id" element={<ConversationPage />} />
            <Route path="/mi-perfil" element={<MyProfilePage />} />
            <Route path="/" element={<Navigate to="/bandeja/sin-asignar" replace />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
