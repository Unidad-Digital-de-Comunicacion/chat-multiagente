package com.udc.operador;

import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

/**
 * Base de todas las pantallas: lo que antes se repetía en cada una. Una llamada
 * de red nunca puede hacerse en el hilo principal (Android lo prohíbe), por eso
 * corre en un Thread aparte.
 */
public abstract class ActividadBase extends AppCompatActivity {

    /** Un pedido de red (o cualquier trabajo) que puede fallar. */
    public interface Tarea {
        void ejecutar() throws Exception;
    }

    public void enSegundoPlano(Tarea tarea) {
        enSegundoPlano(tarea, true, null);
    }

    public void enSegundoPlano(Tarea tarea, boolean avisarSiFalla) {
        enSegundoPlano(tarea, avisarSiFalla, null);
    }

    public void enSegundoPlano(Tarea tarea, Runnable alTerminar) {
        enSegundoPlano(tarea, true, alTerminar);
    }

    /**
     * Corre `tarea` en background. Si lanza una excepción (sin conexión, servidor caído...)
     * avisa con un Toast, salvo que `avisarSiFalla` sea false (refresco automático).
     * `alTerminar`, si hay, corre en el hilo principal al final, haya salido bien o mal.
     */
    public void enSegundoPlano(Tarea tarea, boolean avisarSiFalla, Runnable alTerminar) {
        new Thread(() -> {
            try {
                tarea.ejecutar();
            } catch (Exception e) {
                Log.e(getClass().getSimpleName(), "Error de red", e);
                if (avisarSiFalla) {
                    avisar("No se pudo conectar con el servidor");
                }
            } finally {
                if (alTerminar != null) {
                    runOnUiThread(alTerminar);
                }
            }
        }).start();
    }

    /**
     * Como {@link #enSegundoPlano(Tarea, Runnable)}, pero mientras corre deshabilita `boton` (y
     * `tambienBloquear`) y le pone `textoMientras`, para que se vea que algo está pasando. Al terminar,
     * haya salido bien o mal, todo vuelve a como estaba.
     */
    public void enSegundoPlanoBloqueando(Button boton, String textoMientras, Tarea tarea, View... tambienBloquear) {
        CharSequence textoOriginal = boton.getText();
        boton.setEnabled(false);
        boton.setText(textoMientras);
        for (View vista : tambienBloquear) {
            vista.setEnabled(false);
        }
        enSegundoPlano(tarea, () -> {
            boton.setEnabled(true);
            boton.setText(textoOriginal);
            for (View vista : tambienBloquear) {
                vista.setEnabled(true);
            }
        });
    }

    /** Se puede llamar desde cualquier hilo. */
    public void avisar(String mensaje) {
        runOnUiThread(() -> Toast.makeText(this, mensaje, Toast.LENGTH_LONG).show());
    }

    /** La flecha de "volver" de la barra de arriba, en las pantallas que la muestran. */
    @Override
    public boolean onSupportNavigateUp() {
        finish();
        return true;
    }
}
