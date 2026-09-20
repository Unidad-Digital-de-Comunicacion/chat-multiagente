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

    private final ActividadBase actividad;
    private final long intervaloMs;
    private final ActividadBase.Tarea tarea;
    private final Handler manejador = new Handler(Looper.getMainLooper());
    private final AtomicBoolean enCurso = new AtomicBoolean();
    private final Runnable ciclo = new Runnable() {
        @Override
        public void run() {
            ahora();
            manejador.postDelayed(this, intervaloMs);
        }
    };

    public Sondeo(ActividadBase actividad, long intervaloMs, ActividadBase.Tarea tarea) {
        this.actividad = actividad;
        this.intervaloMs = intervaloMs;
        this.tarea = tarea;
    }

    public void iniciar() {
        manejador.removeCallbacks(ciclo);
        manejador.postDelayed(ciclo, intervaloMs);
    }

    public void detener() {
        manejador.removeCallbacks(ciclo);
    }

    /** Corre la tarea una vez, ya, salvo que la anterior siga en curso. */
    public void ahora() {
        if (enCurso.compareAndSet(false, true)) {
            actividad.enSegundoPlano(tarea, false, () -> enCurso.set(false));
        }
    }
}
