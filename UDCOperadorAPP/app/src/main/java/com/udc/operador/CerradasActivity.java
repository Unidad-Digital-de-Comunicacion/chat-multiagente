package com.udc.operador;

import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.ListView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Conversaciones cerradas del operador (GET /api/core/conversaciones/?bandeja=cerradas).
 * Solo lectura: tocar una la abre en {@link ConversacionActivity} sin poder
 * responder, cerrar, etiquetar ni derivar (Core no permite reabrirlas todavía).
 */
public class CerradasActivity extends AppCompatActivity {

    private static final String TAG = "CerradasActivity";

    private ListView listaCerradas;
    private View progresoCerradas;
    private TextView textSinCerradas;
    private final List<JSONObject> conversaciones = new ArrayList<>();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_cerradas);
        setTitle(R.string.cerradas_titulo);
        getSupportActionBar().setDisplayHomeAsUpEnabled(true);

        listaCerradas = findViewById(R.id.listaCerradas);
        progresoCerradas = findViewById(R.id.progresoCerradas);
        textSinCerradas = findViewById(R.id.textSinCerradas);

        listaCerradas.setOnItemClickListener((parent, view, position, id) ->
                ConversacionActivity.abrir(this, conversaciones.get(position), true));

        cargarCerradas();
    }

    /** La flecha de "volver" de la barra de arriba. */
    @Override
    public boolean onSupportNavigateUp() {
        finish();
        return true;
    }

    private void cargarCerradas() {
        new Thread(() -> {
            try {
                HttpCliente.Respuesta respuesta = HttpCliente.getAutenticado(this, Config.BASE_URL + "/api/core/conversaciones/?bandeja=cerradas");
                if (!respuesta.esExitosa()) {
                    // Con 401 se vuelve a la pantalla principal, que es la que manda al login.
                    runOnUiThread(() -> {
                        Toast.makeText(this, "No se pudieron cargar las cerradas", Toast.LENGTH_SHORT).show();
                        finish();
                    });
                    return;
                }

                JSONArray resultados = new JSONObject(respuesta.cuerpo).getJSONArray("results");
                List<JSONObject> filas = new ArrayList<>();
                for (int i = 0; i < resultados.length(); i++) {
                    filas.add(resultados.getJSONObject(i));
                }
                runOnUiThread(() -> mostrarConversaciones(filas));
            } catch (Exception e) {
                Log.e(TAG, "Error cargando cerradas", e);
                runOnUiThread(() -> {
                    progresoCerradas.setVisibility(View.GONE);
                    Toast.makeText(this, "No se pudo conectar con el servidor", Toast.LENGTH_SHORT).show();
                });
            }
        }).start();
    }

    private void mostrarConversaciones(List<JSONObject> filas) {
        progresoCerradas.setVisibility(View.GONE);
        conversaciones.clear();
        conversaciones.addAll(filas);
        listaCerradas.setAdapter(new ConversacionesAdapter(this, filas));
        textSinCerradas.setVisibility(filas.isEmpty() ? View.VISIBLE : View.GONE);
    }
}
