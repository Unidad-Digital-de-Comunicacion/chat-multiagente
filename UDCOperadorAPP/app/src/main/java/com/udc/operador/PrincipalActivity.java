package com.udc.operador;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
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

    private ListView listaConversaciones;
    private View vistaPerfil;
    private TextView textEmail;
    private final List<Integer> idsConversaciones = new ArrayList<>();
    private int pantallaActual = R.id.menu_sin_asignar;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_principal);

        listaConversaciones = findViewById(R.id.listaConversaciones);
        vistaPerfil = findViewById(R.id.vistaPerfil);
        textEmail = findViewById(R.id.textEmail);
        Button botonCerrarSesion = findViewById(R.id.botonCerrarSesion);

        botonCerrarSesion.setOnClickListener(v -> cerrarSesion());

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
        mostrarPantallaActual();
    }

    private void mostrarPantallaActual() {
        boolean esPerfil = pantallaActual == R.id.menu_perfil;
        listaConversaciones.setVisibility(esPerfil ? View.GONE : View.VISIBLE);
        vistaPerfil.setVisibility(esPerfil ? View.VISIBLE : View.GONE);

        if (esPerfil) {
            cargarPerfil();
        } else {
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

    /** Trae el email del usuario logueado (GET /api/core/users/me/, contrato §1). */
    private void cargarPerfil() {
        new Thread(() -> {
            try {
                HttpCliente.Respuesta respuesta = HttpCliente.getAutenticado(this, Config.BASE_URL + "/api/core/users/me/");
                if (sesionVencida(respuesta)) {
                    return;
                }
                if (!respuesta.esExitosa()) {
                    runOnUiThread(() -> Toast.makeText(this, "No se pudo cargar el perfil", Toast.LENGTH_SHORT).show());
                    return;
                }
                String email = new JSONObject(respuesta.cuerpo).getString("email");
                runOnUiThread(() -> textEmail.setText(email));
            } catch (Exception e) {
                Log.e(TAG, "Error cargando perfil", e);
                runOnUiThread(() -> Toast.makeText(this, "No se pudo conectar con el servidor", Toast.LENGTH_SHORT).show());
            }
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
