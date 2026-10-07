import { useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

// Versión mínima — el contrato de API permite editar nombre/apellido/DNI/
// avatar por PATCH /api/core/users/me/ (multipart/form-data para el
// avatar), pero eso no quedó armado acá. TODO para el equipo: ver
// frontend/admin-panel/src/pages/MyProfilePage.tsx y su AvatarCropper como
// referencia si hace falta ese formulario completo.
export default function MyProfilePage() {
  const { me } = useAuth();
  const navigate = useNavigate();

  if (!me) return null;

  return (
    <div className="page">
      <h1>Mi perfil</h1>
      <div className="card" style={{ maxWidth: 480 }}>
        <p>
          <strong>Nombre:</strong> {me.first_name} {me.last_name}
        </p>
        <p>
          <strong>Email:</strong> {me.email}
        </p>
        <p>
          <strong>DNI:</strong> {me.dni ?? "—"}
        </p>
        <button type="button" className="btn btn-secondary" onClick={() => navigate("/cambiar-contrasena")}>
          Cambiar contraseña
        </button>
      </div>
    </div>
  );
}
