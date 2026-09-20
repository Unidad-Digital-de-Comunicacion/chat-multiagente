package com.udc.operador;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * Guarda los tokens del login (contrato §1) en SharedPreferences, así la
 * sesión sobrevive a cerrar la app: `access` (vence a los 30 minutos, se
 * manda en cada pedido) y `refresh` (vence a los 7 días, sirve para pedir un
 * `access` nuevo sin loguear de nuevo, ver {@link HttpCliente}).
 */
public class Sesion {

    private static final String PREFS_NOMBRE = "sesion";
    private static final String CLAVE_ACCESS = "access_token";
    private static final String CLAVE_REFRESH = "refresh_token";

    public static void guardarTokens(Context context, String access, String refresh) {
        prefs(context).edit()
                .putString(CLAVE_ACCESS, access)
                .putString(CLAVE_REFRESH, refresh)
                .apply();
    }

    /** Reemplaza sólo el access (después de un refresh exitoso). */
    public static void guardarAccess(Context context, String access) {
        prefs(context).edit().putString(CLAVE_ACCESS, access).apply();
    }

    public static String obtenerAccess(Context context) {
        return prefs(context).getString(CLAVE_ACCESS, null);
    }

    public static String obtenerRefresh(Context context) {
        return prefs(context).getString(CLAVE_REFRESH, null);
    }

    /** Borra los tokens guardados (logout). */
    public static void cerrarSesion(Context context) {
        prefs(context).edit().clear().apply();
    }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS_NOMBRE, Context.MODE_PRIVATE);
    }
}
