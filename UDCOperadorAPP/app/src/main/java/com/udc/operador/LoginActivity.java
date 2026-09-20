package com.udc.operador;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONObject;

/**
 * Pantalla de login. Le pega de verdad a Core (POST /api/auth/login/,
 * contrato §1) y, si el usuario/contraseña son correctos, guarda los dos
 * JWT que devuelve con {@link Sesion} y abre la pantalla principal. Si ya
 * hay una sesión guardada, salta directo a la pantalla principal.
 */
public class LoginActivity extends AppCompatActivity {

    private static final String TAG = "LoginActivity";
    private static final String LOGIN_URL = Config.BASE_URL + "/api/auth/login/";

    private EditText editUsuario;
    private EditText editContrasena;
    private Button botonIngresar;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Si ya hay una sesión guardada no hace falta volver a loguearse.
        if (Sesion.obtenerAccess(this) != null) {
            abrirPrincipal();
            return;
        }

        setContentView(R.layout.activity_login);

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
            JSONObject cuerpoPedido = new JSONObject();
            cuerpoPedido.put("email", usuario);
            cuerpoPedido.put("password", contrasena);

            HttpCliente.Respuesta respuesta = HttpCliente.post(LOGIN_URL, cuerpoPedido);
            Log.d(TAG, "Login -> código " + respuesta.codigo);

            if (respuesta.esExitosa()) {
                JSONObject json = new JSONObject(respuesta.cuerpo);
                String access = json.getString("access");
                String refresh = json.getString("refresh");
                runOnUiThread(() -> onLoginExitoso(access, refresh));
            } else {
                runOnUiThread(() -> onLoginError("Usuario o contraseña incorrectos"));
                Log.e(TAG, "Login -> error " + respuesta.cuerpo);
            }
        } catch (Exception e) {
            // Ej.: Core apagado, sin conexión, IP mal escrita, etc.
            Log.e(TAG, "No se pudo conectar con el backend", e);
            runOnUiThread(() -> onLoginError("No se pudo conectar con el servidor"));
        }
    }

    // --- Todo lo que sigue vuelve a correr en el hilo principal (UI). ---

    private void onLoginExitoso(String access, String refresh) {
        Sesion.guardarTokens(this, access, refresh);
        abrirPrincipal();
    }

    private void abrirPrincipal() {
        startActivity(new Intent(this, PrincipalActivity.class));
        finish();
    }

    private void onLoginError(String mensaje) {
        botonIngresar.setEnabled(true);
        Toast.makeText(this, mensaje, Toast.LENGTH_LONG).show();
    }
}
