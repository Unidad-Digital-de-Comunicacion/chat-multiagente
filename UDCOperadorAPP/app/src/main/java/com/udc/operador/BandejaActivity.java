package com.udc.operador;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.ListView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Bandeja de conversaciones (contrato §4.1): dos vistas, "sin asignar" (para
 * tomar una nueva) y "mías" (las que ya tengo asignadas). Tocar una la abre
 * en {@link ConversacionActivity}.
 */
public class BandejaActivity extends AppCompatActivity {

    private static final String TAG = "BandejaActivity";

    private ListView listaConversaciones;
    private final List<Integer> idsConversaciones = new ArrayList<>();
    private String bandejaActual = "sin_asignar";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_bandeja);

        listaConversaciones = findViewById(R.id.listaConversaciones);
        Button botonSinAsignar = findViewById(R.id.botonSinAsignar);
        Button botonMias = findViewById(R.id.botonMias);

        botonSinAsignar.setOnClickListener(v -> cargarBandeja("sin_asignar"));
        botonMias.setOnClickListener(v -> cargarBandeja("mias"));

        listaConversaciones.setOnItemClickListener((parent, view, position, id) -> {
            Intent intent = new Intent(this, ConversacionActivity.class);
            intent.putExtra("conversacion_id", idsConversaciones.get(position));
            startActivity(intent);
        });
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Recarga siempre al volver a esta pantalla (ej. después de tomar o
        // cerrar una conversación) — no hay WebSocket todavía (ver AGENTS.md).
        cargarBandeja(bandejaActual);
    }

    private void cargarBandeja(String bandeja) {
        bandejaActual = bandeja;
        String url = Config.BASE_URL + "/api/core/conversaciones/?bandeja=" + bandeja;
        new Thread(() -> {
            try {
                HttpCliente.Respuesta respuesta = HttpCliente.getAutenticado(this, url);
                if (!respuesta.esExitosa()) {
                    runOnUiThread(() -> Toast.makeText(this, "No se pudo cargar la bandeja", Toast.LENGTH_SHORT).show());
                    return;
                }

                JSONArray resultados = new JSONObject(respuesta.cuerpo).getJSONArray("results");
                List<String> textos = new ArrayList<>();
                List<Integer> ids = new ArrayList<>();
                for (int i = 0; i < resultados.length(); i++) {
                    JSONObject conversacion = resultados.getJSONObject(i);
                    JSONObject contacto = conversacion.getJSONObject("contact");
                    String identificador = contacto.getString("identificador_externo");
                    String canal = conversacion.getString("canal_display");
                    String estado = conversacion.getString("estado_operativo");
                    textos.add(canal + " - " + identificador + " (" + estado + ")");
                    ids.add(conversacion.getInt("id"));
                }
                runOnUiThread(() -> mostrarConversaciones(textos, ids));
            } catch (Exception e) {
                Log.e(TAG, "Error cargando bandeja", e);
                runOnUiThread(() -> Toast.makeText(this, "No se pudo conectar con el servidor", Toast.LENGTH_SHORT).show());
            }
        }).start();
    }

    private void mostrarConversaciones(List<String> textos, List<Integer> ids) {
        idsConversaciones.clear();
        idsConversaciones.addAll(ids);
        listaConversaciones.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_list_item_1, textos));
    }
}
