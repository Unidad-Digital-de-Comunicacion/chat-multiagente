package com.udc.operador;

import static com.udc.operador.HttpCliente.api;
import static com.udc.operador.HttpCliente.ejecutar;
import static com.udc.operador.HttpCliente.json;

import android.widget.EditText;

import androidx.appcompat.app.AlertDialog;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.function.Consumer;

/**
 * Las acciones del menú de tres puntitos de una conversación abierta que se
 * resuelven con un diálogo: aplicar o quitar etiquetas (contrato §4.8) y
 * derivar a otro equipo (§4.7).
 */
public class AccionesConversacion {

    // Etiquetas de sistema que Core sólo deja aplicar con una observación.
    private static final List<String> CODIGOS_CON_OBSERVACION = Arrays.asList("resuelto", "rechazado", "en_pausa");

    private final ActividadBase actividad;
    private final int conversacionId;
    private final ActividadBase.Tarea alCambiarEtiquetas;
    private final Runnable alDerivar;

    /**
     * `alCambiarEtiquetas` corre en background después de aplicar o quitar una etiqueta (para
     * volver a mostrarlas); `alDerivar` corre en el hilo principal, porque la conversación ya no es tuya.
     */
    public AccionesConversacion(ActividadBase actividad, int conversacionId,
                                ActividadBase.Tarea alCambiarEtiquetas, Runnable alDerivar) {
        this.actividad = actividad;
        this.conversacionId = conversacionId;
        this.alCambiarEtiquetas = alCambiarEtiquetas;
        this.alDerivar = alDerivar;
    }

    /** Lista todas las etiquetas de la organización; las ya aplicadas llevan ✓. Tocar una la aplica o la quita. */
    public void mostrarEtiquetas() {
        actividad.enSegundoPlano(() -> {
            HttpCliente.Respuesta catalogo = ejecutar(api().etiquetas());
            HttpCliente.Respuesta aplicadas = ejecutar(api().etiquetasDe(conversacionId));
            if (!catalogo.esExitosa() || !aplicadas.esExitosa()) {
                actividad.avisar("No se pudieron cargar las etiquetas");
                return;
            }

            List<Integer> idsAplicadas = new ArrayList<>();
            JSONArray filasAplicadas = new JSONArray(aplicadas.cuerpo);
            for (int i = 0; i < filasAplicadas.length(); i++) {
                idsAplicadas.add(filasAplicadas.getJSONObject(i).getJSONObject("etiqueta").getInt("id"));
            }

            JSONArray etiquetas = new JSONObject(catalogo.cuerpo).getJSONArray("results");
            List<Integer> ids = new ArrayList<>();
            List<String> codigos = new ArrayList<>();
            List<String> nombres = new ArrayList<>();
            List<String> opciones = new ArrayList<>();
            for (int i = 0; i < etiquetas.length(); i++) {
                JSONObject etiqueta = etiquetas.getJSONObject(i);
                // El estado lo maneja Core (tomar/derivar): aplicarlas a mano lo dejaría inconsistente.
                if (ConversacionesAdapter.esEtiquetaDeEstado(etiqueta)) {
                    continue;
                }
                boolean aplicada = idsAplicadas.contains(etiqueta.getInt("id"));
                ids.add(etiqueta.getInt("id"));
                codigos.add(etiqueta.getString("codigo"));
                nombres.add(etiqueta.getString("nombre"));
                opciones.add((aplicada ? "✓ " : "") + etiqueta.getString("nombre"));
            }

            actividad.runOnUiThread(() -> new AlertDialog.Builder(actividad)
                    .setTitle("Etiquetas (tocá para aplicar o quitar)")
                    .setItems(opciones.toArray(new String[0]), (dialogo, posicion) ->
                            alternarEtiqueta(ids.get(posicion), codigos.get(posicion), nombres.get(posicion),
                                    idsAplicadas.contains(ids.get(posicion))))
                    .show());
        });
    }

    private void alternarEtiqueta(int etiquetaId, String codigo, String nombre, boolean yaAplicada) {
        if (yaAplicada) {
            quitarEtiqueta(etiquetaId);
        } else if (CODIGOS_CON_OBSERVACION.contains(codigo)) {
            pedirObservacion("Motivo para «" + nombre + "»", observacion -> aplicarEtiqueta(etiquetaId, observacion));
        } else {
            aplicarEtiqueta(etiquetaId, "");
        }
    }

    private void aplicarEtiqueta(int etiquetaId, String observacion) {
        actividad.enSegundoPlano(() -> {
            HttpCliente.Respuesta respuesta = ejecutar(api().aplicarEtiqueta(conversacionId,
                    json(new JSONObject().put("etiqueta", etiquetaId).put("observacion", observacion))));
            if (!respuesta.esExitosa()) {
                actividad.avisar(HttpCliente.mensajeDeError(respuesta.cuerpo, "No se pudo aplicar la etiqueta"));
                return;
            }
            actividad.avisar("Etiqueta aplicada");
            alCambiarEtiquetas.ejecutar();
        });
    }

    private void quitarEtiqueta(int etiquetaId) {
        actividad.enSegundoPlano(() -> {
            HttpCliente.Respuesta respuesta = ejecutar(api().quitarEtiqueta(conversacionId, etiquetaId));
            if (!respuesta.esExitosa()) {
                actividad.avisar(HttpCliente.mensajeDeError(respuesta.cuerpo, "No se pudo quitar la etiqueta"));
                return;
            }
            actividad.avisar("Etiqueta quitada");
            alCambiarEtiquetas.ejecutar();
        });
    }

    /** Lista los equipos activos de la organización (GET /teams/) y deriva la conversación al elegido. */
    public void mostrarEquipos() {
        actividad.enSegundoPlano(() -> {
            HttpCliente.Respuesta respuesta = ejecutar(api().equipos());
            if (!respuesta.esExitosa()) {
                actividad.avisar("No se pudieron cargar los equipos");
                return;
            }

            JSONArray equipos = new JSONObject(respuesta.cuerpo).getJSONArray("results");
            List<Integer> ids = new ArrayList<>();
            List<String> nombres = new ArrayList<>();
            for (int i = 0; i < equipos.length(); i++) {
                JSONObject equipo = equipos.getJSONObject(i);
                if (equipo.getBoolean("is_active")) {
                    ids.add(equipo.getInt("id"));
                    nombres.add(equipo.getString("name"));
                }
            }

            actividad.runOnUiThread(() -> new AlertDialog.Builder(actividad)
                    .setTitle("Derivar a...")
                    .setItems(nombres.toArray(new String[0]), (dialogo, posicion) ->
                            pedirObservacion("Motivo de la derivación", observacion ->
                                    derivar(ids.get(posicion), nombres.get(posicion), observacion)))
                    .show());
        });
    }

    private void derivar(int equipoId, String equipoNombre, String observacion) {
        actividad.enSegundoPlano(() -> {
            HttpCliente.Respuesta respuesta = ejecutar(api().derivar(conversacionId,
                    json(new JSONObject().put("team", equipoId).put("observacion", observacion))));
            if (!respuesta.esExitosa()) {
                actividad.avisar(HttpCliente.mensajeDeError(respuesta.cuerpo, "No se pudo derivar la conversación"));
                return;
            }
            actividad.avisar("Conversación derivada a " + equipoNombre);
            actividad.runOnUiThread(alDerivar);
        });
    }

    /** Diálogo con un campo de texto; sólo llama a `alAceptar` si la observación no está vacía. */
    private void pedirObservacion(String titulo, Consumer<String> alAceptar) {
        EditText campo = new EditText(actividad);
        campo.setHint("Observación");
        campo.setPadding(48, 32, 48, 32);
        new AlertDialog.Builder(actividad)
                .setTitle(titulo)
                .setView(campo)
                .setPositiveButton("Aceptar", (dialogo, boton) -> {
                    String texto = campo.getText().toString().trim();
                    if (texto.isEmpty()) {
                        actividad.avisar("La observación no puede estar vacía");
                    } else {
                        alAceptar.accept(texto);
                    }
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }
}
