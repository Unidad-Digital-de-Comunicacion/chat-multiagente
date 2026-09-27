// Tipos según docs/operators-desk-api-contract.md — si algo no coincide con
// lo que devuelve el back de verdad, ese documento (o el Swagger de Core)
// es la fuente de la verdad, no este archivo.

export interface Me {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  dni: string | null;
  avatar: string | null;
  avatar_thumbnail: string | null;
  groups: string[];
  permissions: string[];
  organization_id: number | null;
  is_staff: boolean;
  is_superuser: boolean;
  must_change_password: boolean;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Team {
  id: number;
  name: string;
  members: number[];
  is_active: boolean;
  created_at: string;
}

export type CanalTipo = "WHATSAPP" | "MESSENGER" | "INSTAGRAM" | "WEBCHAT";

export const CANAL_TIPO_LABELS: Record<CanalTipo, string> = {
  WHATSAPP: "WhatsApp",
  MESSENGER: "Messenger",
  INSTAGRAM: "Instagram",
  WEBCHAT: "Webchat",
};

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

export interface EtiquetaAplicada {
  id: number;
  etiqueta: Etiqueta;
  aplicada_por_email: string | null;
  aplicada_at: string;
}

export interface Contacto {
  id: number;
  canal: CanalTipo;
  identificador_externo: string;
  nombre: string;
}

export type ConversacionEstado = "ABIERTA" | "CERRADA";

// Calculado por Core — nunca lo mandes vos, ver §4.1 del contrato de API.
export type EstadoOperativo = "pendiente" | "asignada" | "tomada" | "cerrada";

export const ESTADO_OPERATIVO_LABELS: Record<EstadoOperativo, string> = {
  pendiente: "Pendiente",
  asignada: "Asignada",
  tomada: "Tomada",
  cerrada: "Cerrada",
};

export interface Conversacion {
  id: number;
  contact: Contacto;
  canal: CanalTipo;
  canal_display: string;
  operador: number | null;
  operador_email: string | null;
  team: number | null;
  team_nombre: string | null;
  menu_finalizado: boolean;
  bloqueada_hasta: string | null;
  estado: ConversacionEstado;
  estado_operativo: EstadoOperativo;
  iniciada_at: string;
  cerrada_at: string | null;
  updated_at: string;
}

export type Remitente = "CONTACTO" | "OPERADOR" | "SISTEMA";

export interface Mensaje {
  id: number;
  remitente: Remitente;
  texto: string;
  creado_at: string;
}

export interface NotaInterna {
  id: number;
  operador_email: string | null;
  texto: string;
  creado_at: string;
}

export interface Observacion {
  id: number;
  operador_email: string | null;
  texto: string;
  creado_at: string;
}

// Eventos que llegan por el WebSocket de Conversation Engine — §7.2 del
// contrato de API. Nunca traen el dato real, sólo el aviso de "refrescá X".
export type EventoTipo = "mensaje_nuevo" | "conversacion_actualizada" | "nota_interna_nueva";

export interface EventoOperador {
  tipo: EventoTipo;
  organization_id: number;
  conversacion_id: number;
  team_id: number | null;
  operador_id: number | null;
}
