package com.udc.operador;

import android.os.Handler;
import android.os.Looper;

import java.util.concurrent.TimeUnit;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

/**
 * Conexión WebSocket con Conversation Engine (contrato §7): avisa "algo cambió"
 * y la pantalla vuelve a pedir lo suyo por REST (el evento nunca trae datos).
 * Es un complemento del {@link Sondeo}, no un reemplazo: si el socket se cae,
 * el sondeo sigue trayendo todo. El servidor no reconecta solo, así que acá se
 * reintenta con espera creciente (1 s, 2 s, 4 s... hasta 30 s), y si el servidor
 * rechaza el token (venció) se renueva antes de reintentar.
 */
public class TiempoReal {

    private static final long ESPERA_MAXIMA_MS = 30_000;

    // El ping mantiene viva la conexión (y detecta cuando se cayó sin avisar).
    private static final OkHttpClient CLIENTE = new OkHttpClient.Builder().pingInterval(30, TimeUnit.SECONDS).build();

    private final Runnable alEvento;
    private final Handler manejador = new Handler(Looper.getMainLooper());
    private final Runnable reconectar = this::conectar;
    private WebSocket socket;
    private boolean activo;
    private volatile boolean conectado;
    private long esperaMs = 1_000;

    /** `alEvento` corre en un hilo de OkHttp, no en el principal. */
    public TiempoReal(Runnable alEvento) {
        this.alEvento = alEvento;
    }

    public boolean estaConectado() {
        return conectado;
    }

    public void iniciar() {
        activo = true;
        esperaMs = 1_000;
        conectar();
    }

    public void detener() {
        activo = false;
        conectado = false;
        manejador.removeCallbacks(reconectar);
        if (socket != null) {
            socket.cancel();
            socket = null;
        }
    }

    private void conectar() {
        String access = Sesion.obtenerAccess(App.contexto());
        if (!activo || access == null) {
            return;
        }
        Request pedido = new Request.Builder().url(Config.REALTIME_URL + "/ws/operador/" + access).build();
        socket = CLIENTE.newWebSocket(pedido, new WebSocketListener() {
            @Override
            public void onOpen(WebSocket ws, Response respuesta) {
                esperaMs = 1_000;
                conectado = true;
            }

            @Override
            public void onMessage(WebSocket ws, String texto) {
                alEvento.run();
            }

            @Override
            public void onClosed(WebSocket ws, int codigo, String motivo) {
                reintentar(ws, false);
            }

            @Override
            public void onFailure(WebSocket ws, Throwable error, Response respuesta) {
                // Con el token vencido el servidor rechaza el handshake (contrato §7.1).
                reintentar(ws, respuesta != null);
            }
        });
    }

    /** Vuelve a conectar después de una espera; ignora lo que avise un socket que ya no es el actual. */
    private void reintentar(WebSocket ws, boolean renovarToken) {
        if (!activo || ws != socket) {
            return;
        }
        conectado = false;
        if (renovarToken) {
            HttpCliente.renovarAccess();
        }
        manejador.postDelayed(reconectar, esperaMs);
        esperaMs = Math.min(esperaMs * 2, ESPERA_MAXIMA_MS);
    }
}
