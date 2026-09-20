package com.udc.operador;

import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.SpannableStringBuilder;
import android.util.Log;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ListView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.function.Consumer;

/**
 * Detalle de una conversación (contrato §4.2-§4.8): al abrirla la tomamos
 * para el operador logueado, mostramos el hilo completo y permite responder,
 * cerrar, etiquetar y derivar a otro equipo (menú de los tres puntitos).
 * Las etiquetas aplicadas se ven arriba y las observaciones dentro del
 * hilo. Cargar observaciones sueltas y las notas internas todavía no están.
 */
public class ConversacionActivity extends AppCompatActivity {

    private static final String EXTRA_ID = "conversacion_id";
    private static final String EXTRA_TITULO = "titulo";
    private static final String EXTRA_SUBTITULO = "subtitulo";
    private static final String EXTRA_SOLO_LECTURA = "solo_lectura";

    private static final String TAG = "ConversacionActivity";

    // Etiquetas de sistema que Core sólo deja aplicar con una observación (contrato §4.8).
    private static final List<String> CODIGOS_CON_OBSERVACION = Arrays.asList("resuelto", "rechazado", "en_pausa");

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

    // Cada cuánto se refresca el hilo mientras la pantalla está a la vista (contrato §7.3).
    private static final long INTERVALO_SONDEO_MS = 5_000;
    // El bloqueo dura 2 minutos en Core; se renueva a la mitad de ese tiempo (contrato §4.3).
    private static final long INTERVALO_RENOVACION_MS = 60_000;

    private final List<MensajesAdapter.Linea> lineasMostradas = new ArrayList<>();
    private MensajesAdapter adaptadorMensajes;
    private final Handler manejador = new Handler(Looper.getMainLooper());
    private final Runnable sondeo = new Runnable() {
        @Override
        public void run() {
            refrescarEnSilencio();
            manejador.postDelayed(this, INTERVALO_SONDEO_MS);
        }
    };
    private final Runnable renovacion = new Runnable() {
        @Override
        public void run() {
            renovarBloqueo();
            manejador.postDelayed(this, INTERVALO_RENOVACION_MS);
        }
    };

    private int conversacionId;
    private boolean soloLectura;
    private ListView listaMensajes;
    private TextView textEtiquetas;
    private TextView textNotas;
    private boolean yaMostrada;
    private EditText editMensaje;
    private Button botonEnviar;
    private Button botonCerrar;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_conversacion);

        conversacionId = getIntent().getIntExtra(EXTRA_ID, -1);
        soloLectura = getIntent().getBooleanExtra(EXTRA_SOLO_LECTURA, false);

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

        botonEnviar.setOnClickListener(v -> onEnviarClick());
        botonCerrar.setOnClickListener(v -> onCerrarClick());

        if (soloLectura) {
            // Conversación cerrada: se puede leer, pero no responder, cerrar, etiquetar ni derivar.
            findViewById(R.id.filaRespuesta).setVisibility(View.GONE);
            botonCerrar.setVisibility(View.GONE);
        }

        tomarYCargarMensajes();
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
            refrescarEnSilencio();
        }
        yaMostrada = true;
        if (!soloLectura) {
            manejador.removeCallbacks(sondeo);
            manejador.postDelayed(sondeo, INTERVALO_SONDEO_MS);
            manejador.removeCallbacks(renovacion);
            manejador.postDelayed(renovacion, INTERVALO_RENOVACION_MS);
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        manejador.removeCallbacks(sondeo);
        manejador.removeCallbacks(renovacion);
    }

    /**
     * Vuelve a llamar a `tomar` para que el bloqueo de 2 minutos no venza mientras la pantalla
     * sigue abierta (contrato §4.3). Si Core contesta 400 es que otro operador la tomó después de
     * que el bloqueo venció (por ejemplo si la app estuvo en segundo plano): ya no es tuya.
     * Si falla por conexión no se avisa, se reintenta en el próximo ciclo.
     */
    private void renovarBloqueo() {
        new Thread(() -> {
            try {
                HttpCliente.Respuesta respuesta = HttpCliente.postAutenticado(this, urlConversacion() + "tomar/", new JSONObject());
                if (respuesta.codigo == 400) {
                    runOnUiThread(() -> {
                        Toast.makeText(this, "Otro operador tomó esta conversación", Toast.LENGTH_LONG).show();
                        finish();
                    });
                }
            } catch (Exception e) {
                Log.e(TAG, "Error renovando el bloqueo", e);
            }
        }).start();
    }

    private String urlConversacion() {
        return Config.BASE_URL + "/api/core/conversaciones/" + conversacionId + "/";
    }

    // --- Menú de los tres puntitos: etiquetas y derivar ---

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
            mostrarEtiquetas();
            return true;
        }
        if (item.getItemId() == R.id.menu_notas) {
            abrirNotas();
            return true;
        }
        if (item.getItemId() == R.id.menu_derivar) {
            mostrarEquipos();
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    private interface TareaRed {
        void ejecutar() throws Exception;
    }

    /** Corre un pedido de red en background; si falla por conexión avisa con un Toast. */
    private void enSegundoPlano(TareaRed tarea) {
        new Thread(() -> {
            try {
                tarea.ejecutar();
            } catch (Exception e) {
                Log.e(TAG, "Error de red", e);
                avisar("No se pudo conectar con el servidor");
            }
        }).start();
    }

    private void avisar(String mensaje) {
        runOnUiThread(() -> Toast.makeText(this, mensaje, Toast.LENGTH_LONG).show());
    }

    /** Bloqueante: muestra arriba de la conversación las etiquetas hoy aplicadas (GET .../etiquetas/). */
    private void cargarEtiquetasAplicadas() throws Exception {
        HttpCliente.Respuesta respuesta = HttpCliente.getAutenticado(this, urlConversacion() + "etiquetas/");
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
        HttpCliente.Respuesta respuesta = HttpCliente.getAutenticado(this, urlConversacion() + "notas-internas/");
        if (!respuesta.esExitosa()) {
            return;
        }
        int cantidad = new JSONArray(respuesta.cuerpo).length();
        runOnUiThread(() -> {
            textNotas.setText(getResources().getQuantityString(R.plurals.notas_existen, cantidad, cantidad));
            textNotas.setVisibility(cantidad == 0 ? View.GONE : View.VISIBLE);
        });
    }

    /** En una conversación cerrada las notas se pueden leer pero no escribir. */
    private void abrirNotas() {
        NotasInternasActivity.abrir(this, conversacionId, getIntent().getStringExtra(EXTRA_TITULO), soloLectura);
    }

    /** Lista todas las etiquetas de la organización; las ya aplicadas llevan ✓. Tocar una la aplica o la quita. */
    private void mostrarEtiquetas() {
        enSegundoPlano(() -> {
            HttpCliente.Respuesta catalogo = HttpCliente.getAutenticado(this, Config.BASE_URL + "/api/core/etiquetas/");
            HttpCliente.Respuesta aplicadas = HttpCliente.getAutenticado(this, urlConversacion() + "etiquetas/");
            if (!catalogo.esExitosa() || !aplicadas.esExitosa()) {
                avisar("No se pudieron cargar las etiquetas");
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
                boolean aplicada = idsAplicadas.contains(etiqueta.getInt("id"));
                ids.add(etiqueta.getInt("id"));
                codigos.add(etiqueta.getString("codigo"));
                nombres.add(etiqueta.getString("nombre"));
                opciones.add((aplicada ? "✓ " : "") + etiqueta.getString("nombre"));
            }

            runOnUiThread(() -> new AlertDialog.Builder(this)
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
        enSegundoPlano(() -> {
            JSONObject cuerpo = new JSONObject().put("etiqueta", etiquetaId).put("observacion", observacion);
            HttpCliente.Respuesta respuesta = HttpCliente.postAutenticado(this, urlConversacion() + "etiquetas/", cuerpo);
            if (!respuesta.esExitosa()) {
                avisar(HttpCliente.mensajeDeError(respuesta.cuerpo, "No se pudo aplicar la etiqueta"));
                return;
            }
            avisar("Etiqueta aplicada");
            cargarEtiquetasAplicadas();
        });
    }

    private void quitarEtiqueta(int etiquetaId) {
        enSegundoPlano(() -> {
            HttpCliente.Respuesta respuesta = HttpCliente.deleteAutenticado(this, urlConversacion() + "etiquetas/" + etiquetaId + "/");
            if (!respuesta.esExitosa()) {
                avisar(HttpCliente.mensajeDeError(respuesta.cuerpo, "No se pudo quitar la etiqueta"));
                return;
            }
            avisar("Etiqueta quitada");
            cargarEtiquetasAplicadas();
        });
    }

    /** Lista los equipos de la organización (GET /teams/) y deriva la conversación al elegido (contrato §4.7). */
    private void mostrarEquipos() {
        enSegundoPlano(() -> {
            HttpCliente.Respuesta respuesta = HttpCliente.getAutenticado(this, Config.BASE_URL + "/api/core/teams/");
            if (!respuesta.esExitosa()) {
                avisar("No se pudieron cargar los equipos");
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

            runOnUiThread(() -> new AlertDialog.Builder(this)
                    .setTitle("Derivar a...")
                    .setItems(nombres.toArray(new String[0]), (dialogo, posicion) ->
                            pedirObservacion("Motivo de la derivación", observacion ->
                                    derivar(ids.get(posicion), nombres.get(posicion), observacion)))
                    .show());
        });
    }

    private void derivar(int equipoId, String equipoNombre, String observacion) {
        enSegundoPlano(() -> {
            JSONObject cuerpo = new JSONObject().put("team", equipoId).put("observacion", observacion);
            HttpCliente.Respuesta respuesta = HttpCliente.postAutenticado(this, urlConversacion() + "derivar/", cuerpo);
            if (!respuesta.esExitosa()) {
                avisar(HttpCliente.mensajeDeError(respuesta.cuerpo, "No se pudo derivar la conversación"));
                return;
            }
            avisar("Conversación derivada a " + equipoNombre);
            // Queda sin operador asignado: ya no es tuya, se vuelve a la lista.
            runOnUiThread(this::finish);
        });
    }

    /** Diálogo con un campo de texto; sólo llama a `alAceptar` si la observación no está vacía. */
    private void pedirObservacion(String titulo, Consumer<String> alAceptar) {
        EditText campo = new EditText(this);
        campo.setHint("Observación");
        campo.setPadding(48, 32, 48, 32);
        new AlertDialog.Builder(this)
                .setTitle(titulo)
                .setView(campo)
                .setPositiveButton("Aceptar", (dialogo, boton) -> {
                    String texto = campo.getText().toString().trim();
                    if (texto.isEmpty()) {
                        Toast.makeText(this, "La observación no puede estar vacía", Toast.LENGTH_SHORT).show();
                    } else {
                        alAceptar.accept(texto);
                    }
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }

    /**
     * Reclama la conversación para este operador (contrato §4.3) y después carga el hilo.
     * En solo lectura (conversación cerrada) no la reclama, solo la carga.
     */
    private void tomarYCargarMensajes() {
        new Thread(() -> {
            try {
                if (!soloLectura) {
                    HttpCliente.Respuesta respuesta = HttpCliente.postAutenticado(this, urlConversacion() + "tomar/", new JSONObject());
                    if (!respuesta.esExitosa()) {
                        runOnUiThread(() -> {
                            Toast.makeText(this, "No se pudo tomar la conversación (¿la tiene otro operador?)", Toast.LENGTH_LONG).show();
                            finish();
                        });
                        return;
                    }
                }
                cargarMensajes();
                cargarEtiquetasAplicadas();
                cargarCantidadDeNotas();
            } catch (Exception e) {
                Log.e(TAG, "Error tomando la conversación", e);
                runOnUiThread(() -> {
                    Toast.makeText(this, "No se pudo conectar con el servidor", Toast.LENGTH_SHORT).show();
                    finish();
                });
            }
        }).start();
    }

    /** Bloqueante: llamar sólo desde un hilo de background (los que ya tienen el pedido anterior). */
    private void cargarMensajes() {
        cargarMensajes(true);
    }

    /** `avisarSiFalla` es false en el refresco automático, para no llenar la pantalla de avisos si no hay conexión. */
    private void cargarMensajes(boolean avisarSiFalla) {
        try {
            HttpCliente.Respuesta respuesta = HttpCliente.getAutenticado(this, urlConversacion() + "mensajes/");
            if (!respuesta.esExitosa()) {
                if (avisarSiFalla) {
                    runOnUiThread(() -> Toast.makeText(this, "No se pudo cargar el hilo", Toast.LENGTH_SHORT).show());
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

            HttpCliente.Respuesta observaciones = HttpCliente.getAutenticado(this, urlConversacion() + "observaciones/");
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
        } catch (Exception e) {
            Log.e(TAG, "Error cargando mensajes", e);
            if (avisarSiFalla) {
                runOnUiThread(() -> Toast.makeText(this, "No se pudo conectar con el servidor", Toast.LENGTH_SHORT).show());
            }
        }
    }

    /** Refresco automático del hilo y de las etiquetas (contrato §7.3); sin avisos de error. */
    private void refrescarEnSilencio() {
        new Thread(() -> {
            try {
                cargarMensajes(false);
                cargarEtiquetasAplicadas();
                cargarCantidadDeNotas();
            } catch (Exception e) {
                Log.e(TAG, "Error en el refresco automático", e);
            }
        }).start();
    }

    /** Mientras hay un pedido en curso se bloquea todo, para que se vea que algo está pasando. */
    private void ocupado(boolean si) {
        botonEnviar.setEnabled(!si);
        botonCerrar.setEnabled(!si);
        editMensaje.setEnabled(!si);
        if (!si) {
            botonEnviar.setText(R.string.conversacion_boton_enviar);
            botonCerrar.setText(R.string.conversacion_boton_cerrar);
        }
    }

    private void onEnviarClick() {
        String texto = editMensaje.getText().toString();
        if (texto.isEmpty()) {
            return;
        }
        ocupado(true);
        botonEnviar.setText("Enviando...");
        new Thread(() -> {
            try {
                JSONObject cuerpo = new JSONObject().put("texto", texto);
                HttpCliente.Respuesta respuesta = HttpCliente.postAutenticado(this, urlConversacion() + "responder/", cuerpo);
                if (respuesta.esExitosa()) {
                    // entregado=false: Core lo guardó en el hilo pero el canal no confirmó la entrega (contrato §4.5).
                    boolean entregado = new JSONObject(respuesta.cuerpo).getBoolean("entregado");
                    runOnUiThread(() -> {
                        editMensaje.setText("");
                        if (!entregado) {
                            Toast.makeText(this, "El mensaje quedó en el hilo pero no se pudo entregar al contacto", Toast.LENGTH_LONG).show();
                        }
                    });
                    cargarMensajes();
                } else {
                    runOnUiThread(() -> Toast.makeText(this, "No se pudo enviar el mensaje", Toast.LENGTH_SHORT).show());
                }
            } catch (Exception e) {
                Log.e(TAG, "Error enviando mensaje", e);
                runOnUiThread(() -> Toast.makeText(this, "No se pudo conectar con el servidor", Toast.LENGTH_SHORT).show());
            } finally {
                runOnUiThread(() -> ocupado(false));
            }
        }).start();
    }

    private void onCerrarClick() {
        new AlertDialog.Builder(this)
                .setTitle("Cerrar conversación")
                .setMessage("La conversación se marca como cerrada y, si hay un mensaje de despedida configurado, se le envía al contacto. Ya no vas a poder responderla.")
                .setPositiveButton("Cerrar", (dialogo, boton) -> cerrarConversacion())
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void cerrarConversacion() {
        ocupado(true);
        botonCerrar.setText("Cerrando...");
        new Thread(() -> {
            try {
                HttpCliente.Respuesta respuesta = HttpCliente.postAutenticado(this, urlConversacion() + "cerrar/", new JSONObject());
                if (respuesta.esExitosa()) {
                    runOnUiThread(this::finish);
                    return;
                }
                runOnUiThread(() -> Toast.makeText(this, "No se pudo cerrar la conversación", Toast.LENGTH_SHORT).show());
            } catch (Exception e) {
                Log.e(TAG, "Error cerrando la conversación", e);
                runOnUiThread(() -> Toast.makeText(this, "No se pudo conectar con el servidor", Toast.LENGTH_SHORT).show());
            }
            runOnUiThread(() -> ocupado(false));
        }).start();
    }
}
