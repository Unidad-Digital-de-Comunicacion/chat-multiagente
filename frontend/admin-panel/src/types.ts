// Los 5 grupos de la plataforma (ver users.group_permissions en el back).
// El front nunca decide qué puede hacer cada uno hardcodeando el nombre acá
// — eso lo resuelve el back vía `Me.permissions`. Esta etiqueta es sólo
// para mostrar el nombre lindo de un grupo en la UI.
// Se indexa con nombres de grupo arbitrarios que vienen del back
// (`GROUP_LABELS[g] ?? g`, con fallback al nombre crudo si no está
// mapeado) — necesita el índice abierto de `Record<string, string>` a
// propósito, un tipo con claves literales (`satisfies`) rompería ese
// indexado dinámico bajo `strict`.
// oxlint-disable-next-line anti-slop/no-known-value-widening
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
  deleted_at: string | null;
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
  menu_activo: boolean;
  mensaje_bienvenida: string;
  saludo_inicial: string;
  saludo_area: string;
  mensaje_despedida: string;
  derivacion_texto: string;
  derivacion_mensaje: string;
  mensaje_cierre_inactividad: string;
  mensaje_operador_toma: string;
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

export interface Etiqueta {
  id: number;
  team: number | null;
  codigo: string;
  nombre: string;
  color: string;
  color_texto: string;
  es_sistema: boolean;
  orden: number;
  created_at: string;
  updated_at: string;
}

export type CanalTipo = "WHATSAPP" | "MESSENGER" | "INSTAGRAM" | "WEBCHAT";

export const CANAL_TIPO_LABELS: Record<CanalTipo, string> = {
  WHATSAPP: "WhatsApp",
  MESSENGER: "Messenger",
  INSTAGRAM: "Instagram",
  WEBCHAT: "Webchat",
};

export interface Canal {
  id: number;
  tipo: CanalTipo;
  tipo_display: string;
  api_key_configurada: boolean;
  api_key_preview: string | null;
  api_key_valor: string | null;
  telefono_id: string;
  webhook_url: string | null;
  webhook_secret: string | null;
  activo: boolean;
  ultimo_chequeo_at: string | null;
  ultimo_chequeo_ok: boolean | null;
  ultimo_chequeo_detalle: string;
  updated_at: string;
}

// --------------------------------------------------------------------- //
// Sección "Plataforma" — sólo la ve el superusuario real de plataforma
// (`me.is_superuser && !me.organization_id`, ver `Layout.tsx`). El resto
// de los tipos de acá arriba son siempre de la organización del usuario
// autenticado; éstos abarcan TODAS las organizaciones a la vez.
// --------------------------------------------------------------------- //

export type Plan = "basico" | "profesional" | "enterprise";

export const PLAN_LABELS: Record<Plan, string> = {
  basico: "Básico",
  profesional: "Profesional",
  enterprise: "Enterprise",
};

export interface PlatformOrganization {
  id: number;
  name: string;
  slug: string;
  plan: Plan;
  connection_limit: number;
  user_limit: number;
  monthly_conversation_limit: number;
  is_active: boolean;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlatformUser {
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
  organization_name: string | null;
  is_active: boolean;
  deleted_at: string | null;
  date_joined: string;
  must_change_password: boolean;
}

export type ServicioInterno =
  | "CHANNEL_GATEWAY" | "CONVERSATION_ENGINE" | "OPERATORS_DESK" | "ANALYTICS" | "WEBCHAT";

export const SERVICIO_INTERNO_LABELS: Record<ServicioInterno, string> = {
  CHANNEL_GATEWAY: "Channel Gateway",
  CONVERSATION_ENGINE: "Conversation Engine",
  OPERATORS_DESK: "Operators Desk",
  ANALYTICS: "Analytics",
  WEBCHAT: "Webchat",
};

export interface ServiceToken {
  id: number;
  servicio: ServicioInterno;
  servicio_display: string;
  token_configurado: boolean;
  token_preview: string | null;
  activo: boolean;
  generado_at: string | null;
  updated_at: string;
}

export interface MetaAppConfig {
  app_id: string;
  app_secret_configurada: boolean;
  app_secret_preview: string | null;
  app_secret_valor: string | null;
  updated_at: string;
}

export interface PlatformStatsOrg {
  organization_id: number;
  organization_name: string;
  is_active: boolean;
  usuarios: number;
  user_limit: number;
  equipos: number;
  canales_activos: number;
}

export interface PlatformStats {
  organizaciones_total: number;
  organizaciones_activas: number;
  usuarios_total: number;
  usuarios_activos: number;
  equipos_total: number;
  canales_configurados: number;
  canales_activos: number;
  por_organizacion: PlatformStatsOrg[];
}

export interface ExternalHealthRow {
  organization_id: number;
  organization_name: string;
  tipo: CanalTipo;
  tipo_display: string;
  activo: boolean;
  api_key_configurada: boolean;
  ultimo_chequeo_at: string | null;
  ultimo_chequeo_ok: boolean | null;
  ultimo_chequeo_detalle: string;
}

// --------------------------------------------------------------------- //
// Historial de conversaciones — `GET /api/core/conversaciones/historial/`
// (administradores, `conversations.ver_historial_conversacion`, una sola
// organización) y `GET /api/core/plataforma/historial-conversaciones/`
// (superusuario real, todas las organizaciones — mismo shape de fila,
// `organization_nombre` es el que se usa para agrupar visualmente).
// A propósito NO trae mensajes ni notas internas — sí inicio/derivación/
// fin/etiquetas/observaciones.

export interface ContactoConversacion {
  id: number;
  canal: CanalTipo;
  identificador_externo: string;
  nombre: string;
}

export type ConversacionEstado = "ABIERTA" | "CERRADA";

export interface EtiquetaAplicadaHistorial {
  id: number;
  etiqueta: Etiqueta;
  aplicada_por_email: string | null;
  aplicada_at: string;
}

export interface ObservacionHistorial {
  id: number;
  operador_email: string | null;
  texto: string;
  creado_at: string;
}

export interface ConversacionHistorialRow {
  id: number;
  organization_id: number;
  organization_nombre: string;
  contact: ContactoConversacion;
  canal: CanalTipo;
  canal_display: string;
  team_nombre: string | null;
  derivada_at: string | null;
  operador_email: string | null;
  estado: ConversacionEstado;
  iniciada_at: string;
  cerrada_at: string | null;
  etiquetas: EtiquetaAplicadaHistorial[];
  observaciones: ObservacionHistorial[];
}
