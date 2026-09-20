package com.udc.operador;

import android.content.Context;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * Todo el detalle feo de HttpURLConnection (armar el pedido, mandarlo, leer
 * la respuesta byte a byte) vive acá adentro, una sola vez. El resto de la
 * app sólo llama a {@link #post} (sin token, ej. login) o a
 * {@link #getAutenticado}/{@link #postAutenticado}/{@link #patchAutenticado}
 * (con el token guardado en {@link Sesion}, y refresh automático si
 * venció) y recibe una {@link Respuesta} simple.
 *
 * IMPORTANTE: esto corre en un hilo aparte del principal — quien llame acá
 * tiene que hacerlo desde un Thread de background, nunca directo desde un
 * click.
 */
public class HttpCliente {

    /** Resultado de un pedido: el código HTTP y el texto de la respuesta. */
    public static class Respuesta {
        public final int codigo;
        public final String cuerpo;

        Respuesta(int codigo, String cuerpo) {
            this.codigo = codigo;
            this.cuerpo = cuerpo;
        }

        public boolean esExitosa() {
            return codigo >= 200 && codigo < 300;
        }
    }

    /** POST sin token (login y refresh). */
    public static Respuesta post(String url, JSONObject cuerpoPedido) throws IOException {
        return pedido("POST", url, cuerpoPedido, null);
    }

    private static Respuesta pedido(String metodo, String url, JSONObject cuerpoPedido, String token) throws IOException {
        HttpURLConnection conexion = (HttpURLConnection) new URL(url).openConnection();
        conexion.setRequestMethod(metodo);
        conexion.setRequestProperty("Content-Type", "application/json");
        if (token != null) {
            conexion.setRequestProperty("Authorization", "Bearer " + token);
        }

        if (cuerpoPedido != null) {
            conexion.setDoOutput(true);
            try (OutputStream salida = conexion.getOutputStream()) {
                salida.write(cuerpoPedido.toString().getBytes(StandardCharsets.UTF_8));
            }
        }

        int codigo = conexion.getResponseCode();
        InputStream stream = (codigo >= 200 && codigo < 300) ? conexion.getInputStream() : conexion.getErrorStream();
        return new Respuesta(codigo, leerStream(stream));
    }

    private static String leerStream(InputStream stream) throws IOException {
        if (stream == null) {
            return "";
        }
        StringBuilder resultado = new StringBuilder();
        BufferedReader lector = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8));
        String linea;
        while ((linea = lector.readLine()) != null) {
            resultado.append(linea);
        }
        return resultado.toString();
    }

    // --- Pedidos autenticados, con refresh automático (contrato §1) ---

    /**
     * GET a Core usando el access guardado. Si vino vencido (401), pide uno
     * nuevo con el refresh guardado y reintenta UNA vez. Si el refresh
     * también venció, devuelve el 401 tal cual — la pantalla que llamó
     * decide mandar al login.
     */
    public static Respuesta getAutenticado(Context context, String url) throws IOException {
        return autenticado(context, "GET", url, null);
    }

    public static Respuesta postAutenticado(Context context, String url, JSONObject cuerpoPedido) throws IOException {
        return autenticado(context, "POST", url, cuerpoPedido);
    }

    public static Respuesta patchAutenticado(Context context, String url, JSONObject cuerpoPedido) throws IOException {
        return autenticado(context, "PATCH", url, cuerpoPedido);
    }

    public static Respuesta deleteAutenticado(Context context, String url) throws IOException {
        return autenticado(context, "DELETE", url, null);
    }

    private static Respuesta autenticado(Context context, String metodo, String url, JSONObject cuerpoPedido) throws IOException {
        Respuesta respuesta = pedido(metodo, url, cuerpoPedido, Sesion.obtenerAccess(context));
        if (respuesta.codigo == 401 && refrescarAccess(context)) {
            respuesta = pedido(metodo, url, cuerpoPedido, Sesion.obtenerAccess(context));
        }
        return respuesta;
    }

    /**
     * Mensaje legible de una respuesta de error de la API (contrato §5):
     * `error.detail` — string directo, lista `["msg", ...]` (error que no es
     * de un campo puntual) o `{"campo": ["msg", ...]}` para errores de
     * validación (en ambos casos se usa el primer mensaje).
     */
    public static String mensajeDeError(String cuerpo, String porDefecto) {
        try {
            JSONObject json = new JSONObject(cuerpo);
            Object detalle = json.getJSONObject("error").get("detail");
            if (detalle instanceof JSONObject) {
                JSONObject campos = (JSONObject) detalle;
                Object valor = campos.get(campos.keys().next());
                return valor instanceof JSONArray ? ((JSONArray) valor).getString(0) : valor.toString();
            }
            if (detalle instanceof JSONArray) {
                return ((JSONArray) detalle).getString(0);
            }
            return detalle.toString();
        } catch (Exception e) {
            return porDefecto;
        }
    }

    /** Pide un access nuevo con el refresh guardado. false si el refresh también venció. */
    private static boolean refrescarAccess(Context context) throws IOException {
        String refresh = Sesion.obtenerRefresh(context);
        if (refresh == null) {
            return false;
        }
        try {
            JSONObject cuerpo = new JSONObject().put("refresh", refresh);
            Respuesta respuesta = post(Config.BASE_URL + "/api/auth/refresh/", cuerpo);
            if (!respuesta.esExitosa()) {
                return false;
            }
            Sesion.guardarAccess(context, new JSONObject(respuesta.cuerpo).getString("access"));
            return true;
        } catch (Exception e) {
            return false;
        }
    }
}
