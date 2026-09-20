package com.udc.operador;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ListView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.google.android.material.bottomnavigation.BottomNavigationView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Pantalla principal con menú inferior: conversaciones sin asignar (contrato
 * §4.1 `?bandeja=sin_asignar`), conversaciones mías (`?bandeja=mias`) y
 * perfil (email del usuario logueado + cerrar sesión). Tocar una
 * conversación la abre en {@link ConversacionActivity}.
 */
public class PrincipalActivity extends AppCompatActivity {

    private static final String TAG = "PrincipalActivity";
    private static final String PERFIL_URL = Config.BASE_URL + "/api/core/users/me/";

    private ListView listaConversaciones;
    private View vistaPerfil;
    private TextView textEmail;
    private EditText editNombre;
    private EditText editApellido;
    private EditText editDni;
    private Button botonGuardarPerfil;
    private final List<Integer> idsConversaciones = new ArrayList<>();
    private int pantallaActual = R.id.menu_sin_asignar;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_principal);

        listaConversaciones = findViewById(R.id.listaConversaciones);
        vistaPerfil = findViewById(R.id.vistaPerfil);
        textEmail = findViewById(R.id.textEmail);
        editNombre = findViewById(R.id.editNombre);
        editApellido = findViewById(R.id.editApellido);
        editDni = findViewById(R.id.editDni);
        botonGuardarPerfil = findViewById(R.id.botonGuardarPerfil);

        botonGuardarPerfil.setOnClickListener(v -> guardarPerfil());
        findViewById(R.id.botonCambiarPassword).setOnClickListener(v ->
                startActivity(new Intent(this, CambiarPasswordActivity.class)));
        findViewById(R.id.botonCerrarSesion).setOnClickListener(v -> cerrarSesion());

        listaConversaciones.setOnItemClickListener((parent, view, position, id) -> {
            Intent intent = new Intent(this, ConversacionActivity.class);
            intent.putExtra("conversacion_id", idsConversaciones.get(position));
            startActivity(intent);
        });

        BottomNavigationView menu = findViewById(R.id.menuInferior);
        menu.setOnItemSelectedListener(item -> {
            pantallaActual = item.getItemId();
            mostrarPantallaActual();
            return true;
        });
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Recarga al volver (ej. después de tomar o cerrar una conversación) — no hay WebSocket todavía.
        // El perfil se pide siempre: además de llenar la pantalla, dice si hay que cambiar la contraseña.
        cargarPerfil();
        mostrarPantallaActual();
    }

    private void mostrarPantallaActual() {
        boolean esPerfil = pantallaActual == R.id.menu_perfil;
        listaConversaciones.setVisibility(esPerfil ? View.GONE : View.VISIBLE);
        vistaPerfil.setVisibility(esPerfil ? View.VISIBLE : View.GONE);

        if (!esPerfil) {
            cargarBandeja(pantallaActual == R.id.menu_sin_asignar ? "sin_asignar" : "mias");
        }
    }

    private void cargarBandeja(String bandeja) {
        String url = Config.BASE_URL + "/api/core/conversaciones/?bandeja=" + bandeja;
        new Thread(() -> {
            try {
                HttpCliente.Respuesta respuesta = HttpCliente.getAutenticado(this, url);
                if (sesionVencida(respuesta)) {
                    return;
                }
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
                    String nombre = contacto.getString("nombre");
                    String quien = nombre.isEmpty() ? contacto.getString("identificador_externo") : nombre;
                    String canal = conversacion.getString("canal_display");
                    String equipo = conversacion.isNull("team_nombre") ? "sin equipo" : conversacion.getString("team_nombre");
                    textos.add(canal + " - " + quien + " (" + equipo + ")");
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

    /** Trae el perfil del usuario logueado (GET /api/core/users/me/, contrato §1). */
    private void cargarPerfil() {
        new Thread(() -> {
            try {
                HttpCliente.Respuesta respuesta = HttpCliente.getAutenticado(this, PERFIL_URL);
                if (sesionVencida(respuesta)) {
                    return;
                }
                if (!respuesta.esExitosa()) {
                    runOnUiThread(() -> Toast.makeText(this, "No se pudo cargar el perfil", Toast.LENGTH_SHORT).show());
                    return;
                }
                JSONObject perfil = new JSONObject(respuesta.cuerpo);
                runOnUiThread(() -> mostrarPerfil(perfil));
            } catch (Exception e) {
                Log.e(TAG, "Error cargando perfil", e);
                runOnUiThread(() -> Toast.makeText(this, "No se pudo conectar con el servidor", Toast.LENGTH_SHORT).show());
            }
        }).start();
    }

    private void mostrarPerfil(JSONObject perfil) {
        textEmail.setText(perfil.optString("email"));
        editNombre.setText(texto(perfil, "first_name"));
        editApellido.setText(texto(perfil, "last_name"));
        editDni.setText(texto(perfil, "dni"));

        // Un admin le reseteó la contraseña: no puede seguir sin cambiarla (contrato §1).
        if (perfil.optBoolean("must_change_password")) {
            Intent intent = new Intent(this, CambiarPasswordActivity.class);
            intent.putExtra(CambiarPasswordActivity.EXTRA_OBLIGATORIO, true);
            startActivity(intent);
        }
    }

    /** Un campo que puede venir null en el JSON (ej. `dni`) se muestra como vacío, no como "null". */
    private static String texto(JSONObject json, String campo) {
        return json.isNull(campo) ? "" : json.optString(campo);
    }

    /** PATCH /api/core/users/me/ con nombre, apellido y DNI (nunca grupos ni organización). */
    private void guardarPerfil() {
        String nombre = editNombre.getText().toString().trim();
        String apellido = editApellido.getText().toString().trim();
        String dni = editDni.getText().toString().trim();

        botonGuardarPerfil.setEnabled(false);
        botonGuardarPerfil.setText("Guardando...");
        new Thread(() -> {
            try {
                JSONObject cuerpo = new JSONObject().put("first_name", nombre).put("last_name", apellido).put("dni", dni);
                HttpCliente.Respuesta respuesta = HttpCliente.patchAutenticado(this, PERFIL_URL, cuerpo);
                if (sesionVencida(respuesta)) {
                    return;
                }
                String mensaje = respuesta.esExitosa()
                        ? "Perfil actualizado"
                        : HttpCliente.mensajeDeError(respuesta.cuerpo, "No se pudo guardar el perfil");
                runOnUiThread(() -> Toast.makeText(this, mensaje, Toast.LENGTH_LONG).show());
            } catch (Exception e) {
                Log.e(TAG, "Error guardando perfil", e);
                runOnUiThread(() -> Toast.makeText(this, "No se pudo conectar con el servidor", Toast.LENGTH_SHORT).show());
            }
            runOnUiThread(() -> {
                botonGuardarPerfil.setEnabled(true);
                botonGuardarPerfil.setText(R.string.perfil_boton_guardar);
            });
        }).start();
    }

    /** 401 aunque ya se intentó refrescar el token: la sesión venció, hay que loguear de nuevo. */
    private boolean sesionVencida(HttpCliente.Respuesta respuesta) {
        if (respuesta.codigo != 401) {
            return false;
        }
        runOnUiThread(this::cerrarSesion);
        return true;
    }

    private void cerrarSesion() {
        Sesion.cerrarSesion(this);
        startActivity(new Intent(this, LoginActivity.class));
        finish();
    }
}
