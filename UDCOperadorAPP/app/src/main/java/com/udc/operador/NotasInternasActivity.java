package com.udc.operador;

import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ListView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Notas internas entre operadores de una conversación (contrato §4.10):
 * GET/POST /api/core/conversaciones/{id}/notas-internas/. Nunca salen hacia
 * el contacto, a diferencia de los mensajes. Se refrescan cada 5 segundos
 * mientras la pantalla está a la vista (contrato §7.3).
 */
public class NotasInternasActivity extends AppCompatActivity {

    private static final String TAG = "NotasInternas";
    private static final String EXTRA_ID = "conversacion_id";
    private static final String EXTRA_CONTACTO = "contacto";
    private static final String EXTRA_SOLO_LECTURA = "solo_lectura";
    private static final long INTERVALO_SONDEO_MS = 5_000;

    /**
     * Abre las notas de una conversación; `contacto` es lo que se muestra debajo del título.
     * En solo lectura (conversación cerrada) se pueden leer pero no escribir.
     */
    public static void abrir(Context context, int conversacionId, String contacto, boolean soloLectura) {
        Intent intent = new Intent(context, NotasInternasActivity.class);
        intent.putExtra(EXTRA_ID, conversacionId);
        intent.putExtra(EXTRA_CONTACTO, contacto);
        intent.putExtra(EXTRA_SOLO_LECTURA, soloLectura);
        context.startActivity(intent);
    }

    private int conversacionId;
    private final List<String> notasMostradas = new ArrayList<>();
    private ArrayAdapter<String> adaptador;
    private ListView listaNotas;
    private TextView textSinNotas;
    private EditText editNota;
    private Button botonEnviar;

    private final Handler manejador = new Handler(Looper.getMainLooper());
    private final Runnable sondeo = new Runnable() {
        @Override
        public void run() {
            cargarNotas(false);
            manejador.postDelayed(this, INTERVALO_SONDEO_MS);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_notas_internas);
        setTitle(R.string.notas_titulo);
        getSupportActionBar().setSubtitle(getIntent().getStringExtra(EXTRA_CONTACTO));
        getSupportActionBar().setDisplayHomeAsUpEnabled(true);

        conversacionId = getIntent().getIntExtra(EXTRA_ID, -1);
        listaNotas = findViewById(R.id.listaNotas);
        textSinNotas = findViewById(R.id.textSinNotas);
        editNota = findViewById(R.id.editNota);
        botonEnviar = findViewById(R.id.botonEnviarNota);

        adaptador = new ArrayAdapter<>(this, android.R.layout.simple_list_item_1, notasMostradas);
        listaNotas.setAdapter(adaptador);
        botonEnviar.setOnClickListener(v -> enviarNota());

        if (getIntent().getBooleanExtra(EXTRA_SOLO_LECTURA, false)) {
            findViewById(R.id.filaNota).setVisibility(View.GONE);
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        cargarNotas(true);
        manejador.removeCallbacks(sondeo);
        manejador.postDelayed(sondeo, INTERVALO_SONDEO_MS);
    }

    /** En segundo plano no se sigue consultando. */
    @Override
    protected void onPause() {
        super.onPause();
        manejador.removeCallbacks(sondeo);
    }

    /** La flecha de "volver" de la barra de arriba. */
    @Override
    public boolean onSupportNavigateUp() {
        finish();
        return true;
    }

    private String urlNotas() {
        return Config.BASE_URL + "/api/core/conversaciones/" + conversacionId + "/notas-internas/";
    }

    /** `avisarSiFalla` es false en el refresco automático, para no llenar la pantalla de avisos si no hay conexión. */
    private void cargarNotas(boolean avisarSiFalla) {
        new Thread(() -> {
            try {
                HttpCliente.Respuesta respuesta = HttpCliente.getAutenticado(this, urlNotas());
                if (!respuesta.esExitosa()) {
                    if (avisarSiFalla) {
                        runOnUiThread(() -> Toast.makeText(this, "No se pudieron cargar las notas", Toast.LENGTH_SHORT).show());
                    }
                    return;
                }

                JSONArray notas = new JSONArray(respuesta.cuerpo);
                List<String> textos = new ArrayList<>();
                for (int i = 0; i < notas.length(); i++) {
                    JSONObject nota = notas.getJSONObject(i);
                    textos.add(nota.optString("operador_email") + ": " + nota.optString("texto"));
                }
                runOnUiThread(() -> mostrarNotas(textos));
            } catch (Exception e) {
                Log.e(TAG, "Error cargando notas", e);
                if (avisarSiFalla) {
                    runOnUiThread(() -> Toast.makeText(this, "No se pudo conectar con el servidor", Toast.LENGTH_SHORT).show());
                }
            }
        }).start();
    }

    private void mostrarNotas(List<String> textos) {
        // Si hay notas nuevas (o es la primera carga) se baja al final, como en un chat.
        boolean hayNuevas = textos.size() > notasMostradas.size();
        notasMostradas.clear();
        notasMostradas.addAll(textos);
        adaptador.notifyDataSetChanged();
        if (hayNuevas) {
            listaNotas.setSelection(textos.size() - 1);
        }
        textSinNotas.setVisibility(textos.isEmpty() ? View.VISIBLE : View.GONE);
    }

    private void enviarNota() {
        String texto = editNota.getText().toString().trim();
        if (texto.isEmpty()) {
            return;
        }

        // Mientras se envía se bloquea todo, para que se vea que algo está pasando.
        editNota.setEnabled(false);
        botonEnviar.setEnabled(false);
        botonEnviar.setText("Enviando...");
        new Thread(() -> {
            try {
                JSONObject cuerpo = new JSONObject().put("texto", texto);
                HttpCliente.Respuesta respuesta = HttpCliente.postAutenticado(this, urlNotas(), cuerpo);
                if (respuesta.esExitosa()) {
                    runOnUiThread(() -> editNota.setText(""));
                    cargarNotas(true);
                } else {
                    String mensaje = HttpCliente.mensajeDeError(respuesta.cuerpo, "No se pudo enviar la nota");
                    runOnUiThread(() -> Toast.makeText(this, mensaje, Toast.LENGTH_LONG).show());
                }
            } catch (Exception e) {
                Log.e(TAG, "Error enviando nota", e);
                runOnUiThread(() -> Toast.makeText(this, "No se pudo conectar con el servidor", Toast.LENGTH_SHORT).show());
            }
            runOnUiThread(() -> {
                editNota.setEnabled(true);
                botonEnviar.setEnabled(true);
                botonEnviar.setText(R.string.conversacion_boton_enviar);
            });
        }).start();
    }
}
