package com.udc.operador;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * Guarda y lee el token JWT en el celular usando SharedPreferences: la
 * forma default/estándar de Android para persistir datos chicos (queda
 * guardado aunque cierres la app y la vuelvas a abrir). Para algo tan
 * simple como un token no hace falta ni una base de datos ni una librería
 * externa.
 */
public class Sesion {

    // Nombre del "archivo" de preferencias y la clave dentro de él.
    private static final String PREFS_NOMBRE = "sesion";
    private static final String CLAVE_TOKEN = "jwt_token";

    /** Guarda el token (sobreescribe el anterior si había uno). */
    public static void guardarToken(Context context, String token) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS_NOMBRE, Context.MODE_PRIVATE);
        prefs.edit().putString(CLAVE_TOKEN, token).apply();
    }

    /** Devuelve el token guardado, o null si todavía no se hizo login. */
    public static String obtenerToken(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS_NOMBRE, Context.MODE_PRIVATE);
        return prefs.getString(CLAVE_TOKEN, null);
    }
}
