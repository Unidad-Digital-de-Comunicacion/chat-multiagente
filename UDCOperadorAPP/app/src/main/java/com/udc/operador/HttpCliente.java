package com.udc.operador;

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
 * app (LoginActivity y lo que venga después) sólo llama a
 * {@link #post(String, JSONObject)} y recibe una {@link Respuesta} simple.
 *
 * IMPORTANTE: igual que antes, esto corre en un hilo aparte del principal
 * — quien llame a `post()` tiene que hacerlo desde un Thread de background,
 * nunca directo desde un click.
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
            return codigo == 200;
        }
    }

    /** Manda un POST con `cuerpoPedido` como JSON y devuelve la respuesta. */
    public static Respuesta post(String url, JSONObject cuerpoPedido) throws IOException {
        HttpURLConnection conexion = (HttpURLConnection) new URL(url).openConnection();
        conexion.setRequestMethod("POST");
        conexion.setRequestProperty("Content-Type", "application/json");
        conexion.setDoOutput(true);

        try (OutputStream salida = conexion.getOutputStream()) {
            salida.write(cuerpoPedido.toString().getBytes(StandardCharsets.UTF_8));
        }

        int codigo = conexion.getResponseCode();
        InputStream stream = (codigo == 200) ? conexion.getInputStream() : conexion.getErrorStream();
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
}
