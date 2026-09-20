package com.udc.operador;

import static com.udc.operador.HttpCliente.api;
import static com.udc.operador.HttpCliente.ejecutar;
import static com.udc.operador.HttpCliente.json;

import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;

import org.json.JSONObject;

/**
 * Cambio de contraseña del propio usuario (POST /api/core/users/me/cambiar-
 * password/, contrato §1). Se abre desde Perfil, o solo desde
 * {@link PrincipalActivity} cuando `must_change_password` es true (un admin
 * le reseteó la contraseña): en ese caso, si el operador vuelve atrás sin
 * cambiarla, PrincipalActivity vuelve a abrir esta pantalla.
 */
public class CambiarPasswordActivity extends ActividadBase {

    public static final String EXTRA_OBLIGATORIO = "obligatorio";

    private EditText editPasswordActual;
    private EditText editPasswordNueva;
    private Button botonCambiar;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_cambiar_password);

        editPasswordActual = findViewById(R.id.editPasswordActual);
        editPasswordNueva = findViewById(R.id.editPasswordNueva);
        botonCambiar = findViewById(R.id.botonCambiarPassword);

        if (getIntent().getBooleanExtra(EXTRA_OBLIGATORIO, false)) {
            findViewById(R.id.textAvisoObligatorio).setVisibility(View.VISIBLE);
        }
        botonCambiar.setOnClickListener(v -> cambiar());
    }

    private void cambiar() {
        String actual = editPasswordActual.getText().toString();
        String nueva = editPasswordNueva.getText().toString();
        if (actual.isEmpty() || nueva.isEmpty()) {
            avisar("Completá los dos campos");
            return;
        }

        enSegundoPlanoBloqueando(botonCambiar, "Cambiando...", () -> {
            HttpCliente.Respuesta respuesta = ejecutar(api().cambiarPassword(
                    json(new JSONObject().put("current_password", actual).put("new_password", nueva))));
            if (respuesta.esExitosa()) {
                avisar("Contraseña actualizada");
                runOnUiThread(this::finish);
                return;
            }
            avisar(HttpCliente.mensajeDeError(respuesta.cuerpo, "No se pudo cambiar la contraseña"));
        });
    }
}
