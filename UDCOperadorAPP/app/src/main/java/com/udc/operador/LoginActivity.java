package com.udc.operador;

import android.os.Bundle;
import android.util.Log;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONObject;

/**
 * Pantalla de login. Le pega de verdad a Core (POST /api/auth/login/,
 * ver docs/CONTEXTO_PROYECTO.md sección 9) y, si el usuario/contraseña son
 * correctos, guarda el JWT que devuelve con {@link Sesion}.
 *
 * "10.0.2.2" es una dirección especial que el EMULADOR de Android traduce a
 * "localhost de la máquina donde corre el emulador" — es decir, tu propia
 * PC, donde tenés `docker compose up` corriendo Core en el puerto 8001.
 * Un celular físico no podría usar esta IP (ahí iría la IP de tu PC en la
 * red Wi-Fi, o mejor, la URL real del servidor cuando exista).
 */
public class LoginActivity extends AppCompatActivity {

    private static final String TAG = "LoginActivity";
    private static final String LOGIN_URL = "http://10.0.2.2:8001/api/auth/login/";

    // Referencias a los elementos de la pantalla (activity_login.xml).
    private TextView textTitulo;
    private EditText editUsuario;
    private EditText editContrasena;
    private Button botonIngresar;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_login);

        textTitulo = findViewById(R.id.textTitulo);
        editUsuario = findViewById(R.id.editUsuario);
        editContrasena = findViewById(R.id.editContrasena);
        botonIngresar = findViewById(R.id.botonIngresar);

        botonIngresar.setOnClickListener(v -> onIngresarClick());
    }

    private void onIngresarClick() {
        String usuario = editUsuario.getText().toString();
        String contrasena = editContrasena.getText().toString();

        if (usuario.isEmpty() || contrasena.isEmpty()) {
            Toast.makeText(this, "Completá usuario y contraseña", Toast.LENGTH_SHORT).show();
            return;
        }

        // Mientras esperamos la respuesta, deshabilitamos el botón para que
        // no se pueda tocar "Ingresar" dos veces seguidas.
        botonIngresar.setEnabled(false);

        // Una llamada de red NUNCA puede hacerse en el hilo principal (el
        // que dibuja la pantalla) — Android tira una excepción si lo hacés.
        // Por eso el trabajo pesado (hacerLogin) corre en un Thread aparte.
        new Thread(() -> hacerLogin(usuario, contrasena)).start();
    }

    /** Corre en un hilo de background: acá SÍ se puede hacer la llamada de red. */
    private void hacerLogin(String usuario, String contrasena) {
        try {
            // 1) Armar el pedido: un JSON { "email": ..., "password": ... }
            JSONObject cuerpoPedido = new JSONObject();
            cuerpoPedido.put("email", usuario);
            cuerpoPedido.put("password", contrasena);

            // 2) Mandarlo y esperar la respuesta (todo el detalle feo de
            // HttpURLConnection vive en HttpCliente, no acá).
            HttpCliente.Respuesta respuesta = HttpCliente.post(LOGIN_URL, cuerpoPedido);
            Log.d(TAG, "Login -> código " + respuesta.codigo + ", respuesta: " + respuesta.cuerpo);

            // 3) Interpretar la respuesta. Django devuelve, si está todo
            // bien, { "access": "<jwt>", "refresh": "<jwt>" }.
            if (respuesta.esExitosa()) {
                String token = new JSONObject(respuesta.cuerpo).getString("access");
                runOnUiThread(() -> onLoginExitoso(token));
            } else {
                runOnUiThread(() -> onLoginError("Usuario o contraseña incorrectos"));
            }
        } catch (Exception e) {
            // Ej.: Core apagado, sin conexión, IP mal escrita, etc.
            Log.e(TAG, "No se pudo conectar con el backend", e);
            runOnUiThread(() -> onLoginError("No se pudo conectar con el servidor"));
        }
    }

    // --- Todo lo que sigue vuelve a correr en el hilo principal (UI). ---

    private void onLoginExitoso(String token) {
        Sesion.guardarToken(this, token);
        botonIngresar.setEnabled(true);
        textTitulo.setText("¡Login OK!");
        Toast.makeText(this, "Token guardado", Toast.LENGTH_LONG).show();
    }

    private void onLoginError(String mensaje) {
        botonIngresar.setEnabled(true);
        Toast.makeText(this, mensaje, Toast.LENGTH_LONG).show();
    }
}
