// Los 5 grupos de la plataforma (ver users.group_permissions en el back).
// El front nunca decide qué puede hacer cada uno hardcodeando el nombre acá
// — eso lo resuelve el back vía `Me.permissions`. Esta etiqueta es sólo
// para mostrar el nombre lindo de un grupo en la UI.
export const GROUP_LABELS: Record<string, string> = {
  superusuarios: "Superusuario",
  administradores: "Administrador",
  encargados_difusion: "Encargado de Difusión",
  analistas_datos: "Analista de Datos",
  operadores: "Operador",
};

export interface Group {
  id: number;
  name: string;
}

export interface Me {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  dni: string | null;
  avatar: string | null;
  avatar_thumbnail: string | null;
  groups: string[];
  // Permisos Django efectivos ("app_label.accion_modelo"), unión de todos
  // sus grupos — la fuente de verdad para qué mostrar/ocultar en la UI.
  permissions: string[];
  organization_id: number | null;
  is_staff: boolean;
  is_superuser: boolean;
  must_change_password: boolean;
}

/** Perfil editable por el propio usuario — PATCH /api/core/users/me/. */
export interface MyProfile {
  first_name: string;
  last_name: string;
  email: string;
  dni: string | null;
  avatar: string | null;
  avatar_thumbnail: string | null;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface UserRow {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  dni: string | null;
  avatar: string | null;
  avatar_thumbnail: string | null;
  groups: number[];
  group_names: string[];
  organization: number | null;
  is_active: boolean;
  date_joined: string;
  must_change_password: boolean;
}

export interface Team {
  id: number;
  name: string;
  members: number[];
  is_active: boolean;
  created_at: string;
}

export type MenuTipo = "SUBMENU" | "RESPUESTA" | "DERIVACION" | "VOLVER" | "INICIO" | "TERMINAR";

export const MENU_TIPO_LABELS: Record<MenuTipo, string> = {
  SUBMENU: "Menú (agrupa opciones)",
  RESPUESTA: "Respuesta directa",
  DERIVACION: "Derivación a un equipo",
  VOLVER: "Volver al menú anterior",
  INICIO: "Volver al menú principal",
  TERMINAR: "Terminar la conversación",
};

export interface MenuOpcion {
  id: number;
  texto: string;
  slug: string;
  parent: number | null;
  orden: number;
  tipo: MenuTipo;
  respuesta_texto: string;
  team: number | null;
  activo: boolean;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface MenuOpcionTreeNode {
  id: number;
  texto: string;
  slug: string;
  orden: number;
  tipo: MenuTipo;
  respuesta_texto: string;
  team: number | null;
  activo: boolean;
  hijos: MenuOpcionTreeNode[];
}

export const DIA_SEMANA_LABELS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];

export interface HorarioAtencion {
  id: number;
  dia_semana: number;
  hora_inicio: string;
  hora_fin: string;
  activo: boolean;
}

export type DiaExcepcionalTipo = "FERIADO" | "ASUETO" | "HORARIO_REDUCIDO";

export const DIA_EXCEPCIONAL_TIPO_LABELS: Record<DiaExcepcionalTipo, string> = {
  FERIADO: "Feriado",
  ASUETO: "Asueto",
  HORARIO_REDUCIDO: "Horario reducido",
};

export interface DiaExcepcional {
  id: number;
  fecha: string;
  tipo: DiaExcepcionalTipo;
  hora_inicio: string | null;
  hora_fin: string | null;
  descripcion: string;
  sincronizado: boolean;
  organization: number | null;
}

export interface GrillaSemanal {
  slots: string[];
  celdas: string[];
}

export interface BotMessages {
  mensaje_bienvenida: string;
  saludo_inicial: string;
  saludo_area: string;
  mensaje_despedida: string;
  derivacion_texto: string;
  derivacion_mensaje: string;
  mensaje_cierre_inactividad: string;
  minutos_inactividad_cierre: number;
  segundos_remostrar_menu: number;
  valores_efectivos: Record<string, string>;
  updated_at: string;
}

export interface GrillaDia {
  fecha: string;
  tipo: DiaExcepcionalTipo | "NORMAL";
  celdas: string[];
  descripcion: string;
  /** true si estos datos vienen del catálogo compartido de feriados
   * nacionales (todavía no hay una excepción propia de la organización para
   * esta fecha) — al guardar, se crea la excepción propia igual. */
  compartido: boolean;
}

export interface GrillaDias {
  slots: string[];
  dias: GrillaDia[];
}
