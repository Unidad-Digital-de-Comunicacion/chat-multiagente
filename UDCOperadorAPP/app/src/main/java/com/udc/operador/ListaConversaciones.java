package com.udc.operador;

import static com.udc.operador.HttpCliente.api;
import static com.udc.operador.HttpCliente.ejecutar;

import android.view.LayoutInflater;
import android.view.View;
import android.widget.Button;
import android.widget.ListView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Una lista de conversaciones (GET /api/core/conversaciones/?bandeja=...) con
 * todo lo que la rodea: indicador de carga, texto de lista vacía y el botón
 * "Ver más" (Core devuelve de a 25). La usan "Sin asignar", "Mías" y "Cerradas".
 *
 * Cada "Ver más" suma una página, y cada refresco vuelve a pedir todas las
 * páginas ya cargadas, para no perder lo que el operador ya abrió.
 */
public class ListaConversaciones {

    private static final String PERMISO_TOMAR_SIN_DERIVAR = "conversations.tomar_sin_derivar";

    private final ActividadBase actividad;
    private final ListView lista;
    private final View progreso;
    private final TextView textoVacio;
    private final Runnable alVencerSesion;

    private final List<JSONObject> conversaciones = new ArrayList<>();
    private final ConversacionesAdapter adaptador;
    private final View pie;
    private final Button botonVerMas;
    private boolean pieAgregado;
    // Se leen desde el hilo del refresco automático.
    private volatile int paginasPedidas = 1;
    private volatile String bandejaActual;

    /**
     * `soloLectura` abre las conversaciones sin poder responderlas (las cerradas).
     * `alVencerSesion` corre en el hilo principal si Core contesta 401 aun después de renovar el token.
     */
    public ListaConversaciones(ActividadBase actividad, ListView lista, View progreso, TextView textoVacio,
                               boolean soloLectura, Runnable alVencerSesion) {
        this.actividad = actividad;
        this.lista = lista;
        this.progreso = progreso;
        this.textoVacio = textoVacio;
        this.alVencerSesion = alVencerSesion;

        // Un solo adaptador que se actualiza en el lugar: así el refresco automático no manda la lista al principio.
        adaptador = new ConversacionesAdapter(actividad, conversaciones);
        lista.setAdapter(adaptador);
        lista.setOnItemClickListener((padre, vista, posicion, id) -> {
            JSONObject conversacion = conversaciones.get(posicion);
            // Abrir una conversación la toma; Core no deja tomar una todavía no derivada sin este permiso.
            boolean sinDerivar = "pendiente".equals(conversacion.optString("estado_operativo"));
            if (!soloLectura && sinDerivar && !Sesion.tienePermiso(actividad, PERMISO_TOMAR_SIN_DERIVAR)) {
                actividad.avisar("Esta conversación todavía no fue derivada a un equipo");
                return;
            }
            ConversacionActivity.abrir(actividad, conversacion, soloLectura);
        });

        pie = LayoutInflater.from(actividad).inflate(R.layout.pie_ver_mas, lista, false);
        botonVerMas = pie.findViewById(R.id.botonVerMas);
        botonVerMas.setOnClickListener(v -> verMas());
    }

    public void setTextoVacio(int recurso) {
        textoVacio.setText(recurso);
    }

    /** Al cambiar de pestaña: se vacía la lista para no mostrar las conversaciones de la anterior mientras carga la nueva. */
    public void reiniciar() {
        paginasPedidas = 1;
        conversaciones.clear();
        adaptador.notifyDataSetChanged();
    }

    /** La lista deja de verse (ej. se abrió el perfil): lo que llegue de una carga en curso se descarta. */
    public void ocultar() {
        bandejaActual = null;
        lista.setVisibility(View.GONE);
        progreso.setVisibility(View.GONE);
        textoVacio.setVisibility(View.GONE);
    }

    /** Carga pedida por el operador (abrir la pestaña, "Ver más"): muestra el indicador y avisa si falla. */
    public void cargar(String bandeja) {
        bandejaActual = bandeja;
        lista.setVisibility(View.VISIBLE);
        if (conversaciones.isEmpty()) {
            progreso.setVisibility(View.VISIBLE);
            textoVacio.setVisibility(View.GONE);
        }
        actividad.enSegundoPlano(() -> descargar(bandeja, true), this::terminarCarga);
    }

    /** Refresco automático (para {@link Sondeo}, ya en background): silencioso, y no hace nada si la lista está oculta. */
    public void refrescar() throws Exception {
        String bandeja = bandejaActual;
        if (bandeja != null) {
            descargar(bandeja, false);
        }
    }

    /** Bloqueante: pide todas las páginas cargadas hasta ahora y actualiza la lista. */
    private void descargar(String bandeja, boolean avisarSiFalla) throws Exception {
        List<JSONObject> filas = new ArrayList<>();
        boolean hayMas = false;
        for (int pagina = 1; pagina <= paginasPedidas; pagina++) {
            HttpCliente.Respuesta respuesta = ejecutar(api().conversaciones(bandeja, pagina));
            if (respuesta.codigo == 401) {
                actividad.runOnUiThread(alVencerSesion);
                return;
            }
            if (!respuesta.esExitosa()) {
                if (avisarSiFalla) {
                    actividad.avisar("No se pudo cargar la lista de conversaciones");
                }
                return;
            }

            JSONObject json = new JSONObject(respuesta.cuerpo);
            JSONArray resultados = json.getJSONArray("results");
            for (int i = 0; i < resultados.length(); i++) {
                filas.add(resultados.getJSONObject(i));
            }
            // `next` es null en la última página; si no hay más, no se pide una página que no existe.
            hayMas = !json.isNull("next");
            if (!hayMas) {
                break;
            }
        }
        boolean hayMasFinal = hayMas;
        actividad.runOnUiThread(() -> mostrar(bandeja, filas, hayMasFinal));
    }

    private void mostrar(String bandeja, List<JSONObject> filas, boolean hayMas) {
        // Si mientras llegaba la respuesta se cambió de pestaña, esta lista ya no corresponde.
        if (!bandeja.equals(bandejaActual)) {
            return;
        }
        conversaciones.clear();
        conversaciones.addAll(filas);
        adaptador.notifyDataSetChanged();
        textoVacio.setVisibility(filas.isEmpty() ? View.VISIBLE : View.GONE);

        // El botón sólo está al final de la lista cuando Core dice que hay otra página.
        if (hayMas && !pieAgregado) {
            lista.addFooterView(pie, null, false);
            pieAgregado = true;
        } else if (!hayMas && pieAgregado) {
            lista.removeFooterView(pie);
            pieAgregado = false;
        }
    }

    private void verMas() {
        paginasPedidas++;
        botonVerMas.setEnabled(false);
        botonVerMas.setText(R.string.ver_mas_cargando);
        cargar(bandejaActual);
    }

    /** Fin de una carga pedida por el operador (bien o mal): se apaga el indicador y "Ver más" vuelve a estar disponible. */
    private void terminarCarga() {
        progreso.setVisibility(View.GONE);
        botonVerMas.setEnabled(true);
        botonVerMas.setText(R.string.ver_mas);
    }
}
