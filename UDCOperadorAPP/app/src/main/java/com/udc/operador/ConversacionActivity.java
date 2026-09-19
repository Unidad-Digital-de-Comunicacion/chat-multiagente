package com.udc.operador;

import android.os.Bundle;
import android.util.Log;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ListView;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Detalle de una conversación (contrato §4.2-§4.6): al abrirla la tomamos
 * para el operador logueado, mostramos el hilo completo y permite responder
 * o cerrar. Derivar/etiquetas por conversación/notas internas quedan afuera
 * a propósito — esos endpoints todavía no existen en Core (ver AGENTS.md).
 */
public class ConversacionActivity extends AppCompatActivity {

    private static final String TAG = "ConversacionActivity";

    private int conversacionId;
    private ListView listaMensajes;
    private EditText editMensaje;
    private Button botonEnviar;
    private Button botonCerrar;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_conversacion);

        conversacionId = getIntent().getIntExtra("conversacion_id", -1);
        listaMensajes = findViewById(R.id.listaMensajes);
        editMensaje = findViewById(R.id.editMensaje);
        botonEnviar = findViewById(R.id.botonEnviar);
        botonCerrar = findViewById(R.id.botonCerrar);

        botonEnviar.setOnClickListener(v -> onEnviarClick());
        botonCerrar.setOnClickListener(v -> onCerrarClick());

        tomarYCargarMensajes();
    }

    private String urlConversacion() {
        return Config.BASE_URL + "/api/core/conversaciones/" + conversacionId + "/";
    }

    /** Reclama la conversación para este operador (contrato §4.3) y después carga el hilo. */
    private void tomarYCargarMensajes() {
        new Thread(() -> {
            try {
                HttpCliente.Respuesta respuesta = HttpCliente.postAutenticado(this, urlConversacion() + "tomar/", new JSONObject());
                if (!respuesta.esExitosa()) {
                    runOnUiThread(() -> {
                        Toast.makeText(this, "No se pudo tomar la conversación (¿la tiene otro operador?)", Toast.LENGTH_LONG).show();
                        finish();
                    });
                    return;
                }
                cargarMensajes();
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
        try {
            HttpCliente.Respuesta respuesta = HttpCliente.getAutenticado(this, urlConversacion() + "mensajes/");
            if (!respuesta.esExitosa()) {
                runOnUiThread(() -> Toast.makeText(this, "No se pudo cargar el hilo", Toast.LENGTH_SHORT).show());
                return;
            }

            JSONArray mensajes = new JSONArray(respuesta.cuerpo);
            List<String> textos = new ArrayList<>();
            for (int i = 0; i < mensajes.length(); i++) {
                JSONObject mensaje = mensajes.getJSONObject(i);
                textos.add(mensaje.getString("remitente") + ": " + mensaje.getString("texto"));
            }
            runOnUiThread(() -> listaMensajes.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_list_item_1, textos)));
        } catch (Exception e) {
            Log.e(TAG, "Error cargando mensajes", e);
            runOnUiThread(() -> Toast.makeText(this, "No se pudo conectar con el servidor", Toast.LENGTH_SHORT).show());
        }
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
