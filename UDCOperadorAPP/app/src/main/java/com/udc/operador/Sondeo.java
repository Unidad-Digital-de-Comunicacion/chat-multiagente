package com.udc.operador;

import android.os.Handler;
import android.os.Looper;

import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Repite una tarea de background cada cierto tiempo mientras la pantalla está
 * a la vista (contrato §7.3). Se arranca en `onResume` y se frena en `onPause`,
 * así en segundo plano no consulta nada. Es silencioso si falla, y no apila
 * corridas: si la anterior sigue en curso (red lenta), se salta ese ciclo. La
 * primera vez corre después de un intervalo, no de inmediato; para correrla ya
 * está {@link #ahora}.
 */
public class Sondeo {

    // Con el WebSocket conectado el sondeo es sólo una red de seguridad por si se pierde un evento.
    private static final long INTERVALO_CON_SOCKET_MS = 30_000;

    private final ActividadBase actividad;
    private final long intervaloMs;
    private final ActividadBase.Tarea tarea;
    private final Handler manejador = new Handler(Looper.getMainLooper());
    private final AtomicBoolean enCurso = new AtomicBoolean();
    private TiempoReal tiempoReal;
    private final Runnable ciclo = new Runnable() {
        @Override
        public void run() {
            ahora();
            manejador.postDelayed(this, tiempoReal != null && tiempoReal.estaConectado() ? INTERVALO_CON_SOCKET_MS : intervaloMs);
        }
    };

    public Sondeo(ActividadBase actividad, long intervaloMs, ActividadBase.Tarea tarea) {
        this.actividad = actividad;
        this.intervaloMs = intervaloMs;
        this.tarea = tarea;
    }

    /**
     * Además del intervalo, corre la tarea apenas el WebSocket avisa que algo cambió (ver {@link TiempoReal}).
     * Mientras el socket está conectado el intervalo pasa a 30 s.
     */
    public Sondeo conTiempoReal() {
        tiempoReal = new TiempoReal(this::ahora);
        return this;
    }

    public void iniciar() {
        manejador.removeCallbacks(ciclo);
        manejador.postDelayed(ciclo, intervaloMs);
        if (tiempoReal != null) {
            tiempoReal.iniciar();
        }
    }

    public void detener() {
        manejador.removeCallbacks(ciclo);
        if (tiempoReal != null) {
            tiempoReal.detener();
        }
    }

    /** Corre la tarea una vez, ya, salvo que la anterior siga en curso. */
    public void ahora() {
        if (enCurso.compareAndSet(false, true)) {
            actividad.enSegundoPlano(tarea, false, () -> enCurso.set(false));
        }
    }
}
