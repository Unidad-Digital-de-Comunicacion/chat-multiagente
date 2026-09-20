package com.udc.operador;

import static com.udc.operador.HttpCliente.api;
import static com.udc.operador.HttpCliente.ejecutar;
import static com.udc.operador.HttpCliente.json;

import android.content.Intent;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;

import org.json.JSONObject;

/**
 * Pantalla de login (POST /api/auth/login/, contrato §1): guarda los dos JWT
 * en {@link Sesion} y abre la pantalla principal. Si ya hay una sesión
 * guardada, salta directo a la pantalla principal.
 */
public class LoginActivity extends ActividadBase {

    private EditText editUsuario;
    private EditText editContrasena;
    private Button botonIngresar;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        if (Sesion.obtenerAccess(this) != null) {
            abrirPrincipal();
            return;
        }

        setContentView(R.layout.activity_login);
        editUsuario = findViewById(R.id.editUsuario);
        editContrasena = findViewById(R.id.editContrasena);
        botonIngresar = findViewById(R.id.botonIngresar);
        botonIngresar.setOnClickListener(v -> ingresar());
    }

    private void ingresar() {
        String usuario = editUsuario.getText().toString();
        String contrasena = editContrasena.getText().toString();
        if (usuario.isEmpty() || contrasena.isEmpty()) {
            avisar("Completá usuario y contraseña");
            return;
        }

        enSegundoPlanoBloqueando(botonIngresar, "Ingresando...", () -> {
            HttpCliente.Respuesta respuesta = ejecutar(api().login(
                    json(new JSONObject().put("email", usuario).put("password", contrasena))));
            if (!respuesta.esExitosa()) {
                avisar("Usuario o contraseña incorrectos");
                return;
            }
            JSONObject tokens = new JSONObject(respuesta.cuerpo);
            Sesion.guardarTokens(this, tokens.getString("access"), tokens.getString("refresh"));
            runOnUiThread(this::abrirPrincipal);
        });
    }

    private void abrirPrincipal() {
        startActivity(new Intent(this, PrincipalActivity.class));
        finish();
    }
}
