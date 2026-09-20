package com.udc.operador;

import static com.udc.operador.HttpCliente.api;
import static com.udc.operador.HttpCliente.ejecutar;
import static com.udc.operador.HttpCliente.json;

import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.text.SpannableStringBuilder;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ListView;
import android.widget.TextView;

import androidx.appcompat.app.AlertDialog;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Detalle de una conversación (contrato §4.2-§4.10): al abrirla se toma para
 * el operador, se muestra el hilo como burbujas y se puede responder, cerrar,
 * etiquetar, derivar y ver las notas internas. Una conversación cerrada se
 * abre en solo lectura. Las etiquetas y la cantidad de notas se ven arriba;
 * las observaciones, dentro del hilo.
 */
public class ConversacionActivity extends ActividadBase {

    private static final String EXTRA_ID = "conversacion_id";
    private static final String EXTRA_TITULO = "titulo";
    private static final String EXTRA_SUBTITULO = "subtitulo";
    private static final String EXTRA_SOLO_LECTURA = "solo_lectura";

    // Cada cuánto se refresca el hilo mientras la pantalla está a la vista.
    private static final long INTERVALO_SONDEO_MS = 5_000;
    // El bloqueo dura 2 minutos en Core; se renueva a la mitad de ese tiempo (contrato §4.3).
    private static final long INTERVALO_RENOVACION_MS = 60_000;

    /**
     * Abre la conversación de una fila de la lista (GET /conversaciones/). El
     * contacto viaja en el Intent para mostrarlo arriba sin otro pedido:
     * su nombre (o su número si no tiene) y el canal.
     */
    public static void abrir(Context context, JSONObject conversacion, boolean soloLectura) {
        JSONObject contacto = conversacion.optJSONObject("contact");
        String nombre = contacto.optString("nombre");
        String numero = contacto.optString("identificador_externo");
        String canal = conversacion.optString("canal_display");

        Intent intent = new Intent(context, ConversacionActivity.class);
        intent.putExtra(EXTRA_ID, conversacion.optInt("id"));
        intent.putExtra(EXTRA_TITULO, nombre.isEmpty() ? numero : nombre);
        intent.putExtra(EXTRA_SUBTITULO, nombre.isEmpty() ? canal : canal + " · " + numero);
        intent.putExtra(EXTRA_SOLO_LECTURA, soloLectura);
        context.startActivity(intent);
    }

    private int conversacionId;
    private boolean soloLectura;
    private boolean yaMostrada;
    private AccionesConversacion acciones;

    private final List<MensajesAdapter.Linea> lineasMostradas = new ArrayList<>();
    private MensajesAdapter adaptadorMensajes;
    private ListView listaMensajes;
    private TextView textEtiquetas;
    private TextView textNotas;
    private EditText editMensaje;
    private Button botonEnviar;
    private Button botonCerrar;

    private final Sondeo sondeo = new Sondeo(this, INTERVALO_SONDEO_MS, this::refrescar).conTiempoReal();
    private final Sondeo renovacion = new Sondeo(this, INTERVALO_RENOVACION_MS, this::renovarBloqueo);

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_conversacion);

        conversacionId = getIntent().getIntExtra(EXTRA_ID, -1);
        soloLectura = getIntent().getBooleanExtra(EXTRA_SOLO_LECTURA, false);
        acciones = new AccionesConversacion(this, conversacionId, this::cargarEtiquetasAplicadas, this::finish);

        // Arriba: con quién se está hablando (y si la conversación está cerrada).
        setTitle(getIntent().getStringExtra(EXTRA_TITULO));
        getSupportActionBar().setSubtitle(getIntent().getStringExtra(EXTRA_SUBTITULO) + (soloLectura ? " · cerrada" : ""));

        listaMensajes = findViewById(R.id.listaMensajes);
        // Un solo adaptador que se actualiza en el lugar: así el refresco automático no mueve la lectura.
        adaptadorMensajes = new MensajesAdapter(this, lineasMostradas);
        listaMensajes.setAdapter(adaptadorMensajes);
        textEtiquetas = findViewById(R.id.textEtiquetas);
        textNotas = findViewById(R.id.textNotas);
        textNotas.setOnClickListener(v -> abrirNotas());
        editMensaje = findViewById(R.id.editMensaje);
        botonEnviar = findViewById(R.id.botonEnviar);
        botonCerrar = findViewById(R.id.botonCerrar);
        botonEnviar.setOnClickListener(v -> enviar());
        botonCerrar.setOnClickListener(v -> confirmarCierre());

        if (soloLectura) {
            // Conversación cerrada: se puede leer, pero no responder, cerrar, etiquetar ni derivar.
            findViewById(R.id.filaRespuesta).setVisibility(View.GONE);
            botonCerrar.setVisibility(View.GONE);
        }

        tomarYCargar();
    }

    /**
     * Una conversación cerrada no cambia ni se toma, así que sólo las abiertas se refrescan
     * y renuevan el bloqueo. Todo se pausa en segundo plano.
     */
    @Override
    protected void onResume() {
        super.onResume();
        // Al volver de otra pantalla (ej. las notas internas) se actualiza lo que pudo haber cambiado.
        // La primera vez no: ya se está cargando todo desde onCreate.
        if (yaMostrada) {
            sondeo.ahora();
        }
        yaMostrada = true;
        if (!soloLectura) {
            sondeo.iniciar();
            renovacion.iniciar();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        sondeo.detener();
        renovacion.detener();
    }

    // --- Menú de los tres puntitos: etiquetas, notas internas y derivar ---

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        if (soloLectura) {
            return false;
        }
        getMenuInflater().inflate(R.menu.menu_conversacion, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == R.id.menu_etiquetas) {
            acciones.mostrarEtiquetas();
            return true;
        }
        if (item.getItemId() == R.id.menu_notas) {
            abrirNotas();
            return true;
        }
        if (item.getItemId() == R.id.menu_derivar) {
            acciones.mostrarEquipos();
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    /** En una conversación cerrada las notas se pueden leer pero no escribir. */
    private void abrirNotas() {
        NotasInternasActivity.abrir(this, conversacionId, getIntent().getStringExtra(EXTRA_TITULO), soloLectura);
    }

    // --- Carga del contenido ---

    /**
     * Reclama la conversación para este operador (contrato §4.3) y después carga todo.
     * En solo lectura (conversación cerrada) no la reclama, solo la carga.
     */
    private void tomarYCargar() {
        enSegundoPlano(() -> {
            if (!soloLectura) {
                HttpCliente.Respuesta respuesta = ejecutar(api().tomar(conversacionId));
                if (!respuesta.esExitosa()) {
                    avisar("No se pudo tomar la conversación (¿la tiene otro operador?)");
                    runOnUiThread(this::finish);
                    return;
                }
            }
            cargarMensajes(true);
            cargarEtiquetasAplicadas();
            cargarCantidadDeNotas();
        });
    }

    /** Refresco automático (contrato §7.3), ya en background: lo corre {@link Sondeo}. */
    private void refrescar() throws Exception {
        cargarMensajes(false);
        cargarEtiquetasAplicadas();
        cargarCantidadDeNotas();
    }

    /**
     * Vuelve a llamar a `tomar` para que el bloqueo de 2 minutos no venza mientras la pantalla sigue
     * abierta. Si Core contesta 400 es que otro operador la tomó después de que el bloqueo venció
     * (por ejemplo si la app estuvo en segundo plano): ya no es tuya. Si falla por conexión no se
     * avisa, se reintenta en el próximo ciclo.
     */
    private void renovarBloqueo() throws Exception {
        if (ejecutar(api().tomar(conversacionId)).codigo == 400) {
            avisar("Otro operador tomó esta conversación");
            runOnUiThread(this::finish);
        }
    }

    /** Bloqueante: llamar sólo desde un hilo de background. */
    private void cargarMensajes(boolean avisarSiFalla) throws Exception {
        HttpCliente.Respuesta respuesta = ejecutar(api().mensajes(conversacionId));
        if (!respuesta.esExitosa()) {
            if (avisarSiFalla) {
                avisar("No se pudo cargar el hilo");
            }
            return;
        }

        // Los mensajes y las observaciones se mezclan en un solo hilo, ordenados por fecha.
        List<MensajesAdapter.Linea> lineas = new ArrayList<>();
        String contacto = getIntent().getStringExtra(EXTRA_TITULO);
        JSONArray mensajes = new JSONArray(respuesta.cuerpo);
        for (int i = 0; i < mensajes.length(); i++) {
            JSONObject mensaje = mensajes.getJSONObject(i);
            MensajesAdapter.Tipo tipo;
            String remitente;
            switch (mensaje.getString("remitente")) {
                case "CONTACTO":
                    tipo = MensajesAdapter.Tipo.CONTACTO;
                    remitente = contacto;
                    break;
                case "OPERADOR":
                    tipo = MensajesAdapter.Tipo.OPERADOR;
                    // Core todavía no dice qué operador escribió cada mensaje; cuando lo mande (`operador_email`), se muestra.
                    remitente = mensaje.isNull("operador_email") ? "Operador" : mensaje.getString("operador_email");
                    break;
                default:
                    tipo = MensajesAdapter.Tipo.SISTEMA;
                    remitente = "Sistema";
            }
            lineas.add(new MensajesAdapter.Linea(tipo, remitente, mensaje.getString("texto"), mensaje.getString("creado_at")));
        }

        HttpCliente.Respuesta observaciones = ejecutar(api().observaciones(conversacionId));
        if (observaciones.esExitosa()) {
            JSONArray filas = new JSONArray(observaciones.cuerpo);
            for (int i = 0; i < filas.length(); i++) {
                JSONObject fila = filas.getJSONObject(i);
                lineas.add(new MensajesAdapter.Linea(MensajesAdapter.Tipo.OBSERVACION,
                        "📝 Observación · " + fila.optString("operador_email"), fila.getString("texto"), fila.getString("creado_at")));
            }
        }
        lineas.sort((a, b) -> a.momento().compareTo(b.momento()));

        runOnUiThread(() -> {
            // Si hay líneas nuevas (o es la primera carga) se baja al final, como en cualquier chat.
            boolean hayNuevas = lineas.size() > lineasMostradas.size();
            lineasMostradas.clear();
            lineasMostradas.addAll(lineas);
            adaptadorMensajes.notifyDataSetChanged();
            if (hayNuevas) {
                listaMensajes.setSelection(lineas.size() - 1);
            }
        });
    }

    /** Bloqueante: muestra arriba de la conversación las etiquetas hoy aplicadas (GET .../etiquetas/). */
    private void cargarEtiquetasAplicadas() throws Exception {
        HttpCliente.Respuesta respuesta = ejecutar(api().etiquetasDe(conversacionId));
        if (!respuesta.esExitosa()) {
            return;
        }
        JSONArray aplicadas = new JSONArray(respuesta.cuerpo);
        JSONArray etiquetas = new JSONArray();
        for (int i = 0; i < aplicadas.length(); i++) {
            etiquetas.put(aplicadas.getJSONObject(i).getJSONObject("etiqueta"));
        }
        // Mismo dibujo que en las listas: cada etiqueta con su color y el color de su letra.
        SpannableStringBuilder texto = ConversacionesAdapter.textoDeEtiquetas(etiquetas);
        runOnUiThread(() -> {
            textEtiquetas.setText(texto);
            textEtiquetas.setVisibility(texto.length() == 0 ? View.GONE : View.VISIBLE);
        });
    }

    /** Bloqueante: si la conversación tiene notas internas, muestra arriba cuántas son (GET .../notas-internas/). */
    private void cargarCantidadDeNotas() throws Exception {
        HttpCliente.Respuesta respuesta = ejecutar(api().notas(conversacionId));
        if (!respuesta.esExitosa()) {
            return;
        }
        int cantidad = new JSONArray(respuesta.cuerpo).length();
        runOnUiThread(() -> {
            textNotas.setText(getResources().getQuantityString(R.plurals.notas_existen, cantidad, cantidad));
            textNotas.setVisibility(cantidad == 0 ? View.GONE : View.VISIBLE);
        });
    }

    // --- Responder y cerrar ---

    private void enviar() {
        String texto = editMensaje.getText().toString();
        if (texto.isEmpty()) {
            return;
        }
        enSegundoPlanoBloqueando(botonEnviar, "Enviando...", () -> {
            HttpCliente.Respuesta respuesta = ejecutar(api().responder(conversacionId, json(new JSONObject().put("texto", texto))));
            if (!respuesta.esExitosa()) {
                avisar(HttpCliente.mensajeDeError(respuesta.cuerpo, "No se pudo enviar el mensaje"));
                return;
            }
            runOnUiThread(() -> editMensaje.setText(""));
            // entregado=false: Core lo guardó en el hilo pero el canal no confirmó la entrega (contrato §4.5).
            if (!new JSONObject(respuesta.cuerpo).getBoolean("entregado")) {
                avisar("El mensaje quedó en el hilo pero no se pudo entregar al contacto");
            }
            cargarMensajes(true);
        }, botonCerrar, editMensaje);
    }

    private void confirmarCierre() {
        new AlertDialog.Builder(this)
                .setTitle("Cerrar conversación")
                .setMessage("La conversación se marca como cerrada y, si hay un mensaje de despedida configurado, se le envía al contacto. Ya no vas a poder responderla.")
                .setPositiveButton("Cerrar", (dialogo, boton) -> cerrar())
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void cerrar() {
        enSegundoPlanoBloqueando(botonCerrar, "Cerrando...", () -> {
            HttpCliente.Respuesta respuesta = ejecutar(api().cerrar(conversacionId));
            if (respuesta.esExitosa()) {
                runOnUiThread(this::finish);
                return;
            }
            avisar(HttpCliente.mensajeDeError(respuesta.cuerpo, "No se pudo cerrar la conversación"));
        }, botonEnviar, editMensaje);
    }
}
