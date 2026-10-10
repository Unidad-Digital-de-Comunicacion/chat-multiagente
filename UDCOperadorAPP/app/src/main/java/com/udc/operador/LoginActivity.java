package com.udc.operador;

import static com.udc.operador.HttpCliente.api;
import static com.udc.operador.HttpCliente.ejecutar;
import static com.udc.operador.HttpCliente.json;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Spinner;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

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
        configurarUsuariosDemo();
    }

    // --- Sólo para pruebas: usuarios de `manage.py seed_ucd_demo` (services/core/organizations/management/commands) ---

    private static final String PASSWORD_DEMO = "Contrasena-123";
    private static final String[][] USUARIOS_DEMO = {
            {"Superusuario (plataforma)", "superusuario@ucd.demo"},
            {"Administrador", "admin@ucd.demo"},
            {"Encargado de difusión", "difusion@ucd.demo"},
            {"Agente 1 (Soporte)", "agente1@ucd.demo"},
            {"Agente 2 (Soporte, Ventas)", "agente2@ucd.demo"},
            {"Agente 3 (Ventas)", "agente3@ucd.demo"},
            {"Agente 4 (Postventa)", "agente4@ucd.demo"},
            {"Agente 5 (Soporte, Postventa)", "agente5@ucd.demo"},
    };

    /** Se muestra en cualquier build (por ahora todas son de prueba); quitar antes de publicar una release. */
    private void configurarUsuariosDemo() {
        List<String> opciones = new ArrayList<>();
        opciones.add("Usuarios de prueba…");
        for (String[] usuario : USUARIOS_DEMO) {
            opciones.add(usuario[0] + " — " + usuario[1]);
        }

        Spinner spinner = findViewById(R.id.spinnerUsuariosDemo);
        spinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, opciones));
        spinner.setVisibility(View.VISIBLE);
        spinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> padre, View vista, int posicion, long id) {
                if (posicion == 0) {
                    return;
                }
                editUsuario.setText(USUARIOS_DEMO[posicion - 1][1]);
                editContrasena.setText(PASSWORD_DEMO);
            }

            @Override
            public void onNothingSelected(AdapterView<?> padre) {
            }
        });
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
