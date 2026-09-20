package com.udc.operador;

import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
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

    // Cada cuánto se refresca la lista mientras la pantalla está a la vista (contrato §7.3).
    private static final long INTERVALO_SONDEO_MS = 10_000;

    private final List<JSONObject> conversaciones = new ArrayList<>();
    private ConversacionesAdapter adaptador;
    private int pantallaActual = R.id.menu_sin_asignar;

    private final Handler manejador = new Handler(Looper.getMainLooper());
    private final Runnable sondeo = new Runnable() {
        @Override
        public void run() {
            if (pantallaActual != R.id.menu_perfil) {
                cargarBandeja(nombreBandeja(), false);
            }
            manejador.postDelayed(this, INTERVALO_SONDEO_MS);
        }
    };

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
        Button botonCambiarPassword = findViewById(R.id.botonCambiarPassword);
        Button botonCerrarSesion = findViewById(R.id.botonCerrarSesion);

        botonGuardarPerfil.setOnClickListener(v -> guardarPerfil());
        botonCambiarPassword.setOnClickListener(v ->
                startActivity(new Intent(this, CambiarPasswordActivity.class)));
        botonCerrarSesion.setOnClickListener(v -> cerrarSesion());

        // Un solo adaptador que se actualiza en el lugar: así el refresco automático no manda la lista al principio.
        adaptador = new ConversacionesAdapter(this, conversaciones);
        listaConversaciones.setAdapter(adaptador);
        listaConversaciones.setOnItemClickListener((parent, view, position, id) ->
                ConversacionActivity.abrir(this, conversaciones.get(position), false));

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

        manejador.removeCallbacks(sondeo);
        manejador.postDelayed(sondeo, INTERVALO_SONDEO_MS);
    }

    /** En segundo plano no se sigue consultando (contrato §7.3). */
    @Override
    protected void onPause() {
        super.onPause();
        manejador.removeCallbacks(sondeo);
    }

    // --- Menú de los tres puntitos: "Ver cerradas", sólo en la pestaña Mías ---

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        getMenuInflater().inflate(R.menu.menu_mias, menu);
        return true;
    }

    @Override
    public boolean onPrepareOptionsMenu(Menu menu) {
        menu.findItem(R.id.menu_ver_cerradas).setVisible(pantallaActual == R.id.menu_mias);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        if (item.getItemId() == R.id.menu_ver_cerradas) {
            startActivity(new Intent(this, CerradasActivity.class));
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    private void mostrarPantallaActual() {
        boolean esPerfil = pantallaActual == R.id.menu_perfil;
        listaConversaciones.setVisibility(esPerfil ? View.GONE : View.VISIBLE);
        vistaPerfil.setVisibility(esPerfil ? View.VISIBLE : View.GONE);
        invalidateOptionsMenu();

        if (!esPerfil) {
            cargarBandeja(nombreBandeja(), true);
        }
    }

    private String nombreBandeja() {
        return pantallaActual == R.id.menu_sin_asignar ? "sin_asignar" : "mias";
    }

    /** `avisarSiFalla` es false en el refresco automático, para no llenar la pantalla de avisos si no hay conexión. */
    private void cargarBandeja(String bandeja, boolean avisarSiFalla) {
        String url = Config.BASE_URL + "/api/core/conversaciones/?bandeja=" + bandeja;
        new Thread(() -> {
            try {
                HttpCliente.Respuesta respuesta = HttpCliente.getAutenticado(this, url);
                if (sesionVencida(respuesta)) {
                    return;
                }
                if (!respuesta.esExitosa()) {
                    if (avisarSiFalla) {
                        runOnUiThread(() -> Toast.makeText(this, "No se pudo cargar la bandeja", Toast.LENGTH_SHORT).show());
                    }
                    return;
                }

                JSONArray resultados = new JSONObject(respuesta.cuerpo).getJSONArray("results");
                List<JSONObject> filas = new ArrayList<>();
                for (int i = 0; i < resultados.length(); i++) {
                    filas.add(resultados.getJSONObject(i));
                }
                runOnUiThread(() -> mostrarConversaciones(bandeja, filas));
            } catch (Exception e) {
                Log.e(TAG, "Error cargando bandeja", e);
                if (avisarSiFalla) {
                    runOnUiThread(() -> Toast.makeText(this, "No se pudo conectar con el servidor", Toast.LENGTH_SHORT).show());
                }
            }
        }).start();
    }

    private void mostrarConversaciones(String bandeja, List<JSONObject> filas) {
        // Si mientras llegaba la respuesta se cambió de pestaña, esta lista ya no corresponde.
        if (pantallaActual == R.id.menu_perfil || !bandeja.equals(nombreBandeja())) {
            return;
        }
        conversaciones.clear();
        conversaciones.addAll(filas);
        adaptador.notifyDataSetChanged();
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
