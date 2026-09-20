package com.udc.operador;

import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONObject;

/**
 * Cambio de contraseña del propio usuario (POST /api/core/users/me/cambiar-
 * password/, contrato §1). Se abre desde Perfil, o solo desde
 * {@link PrincipalActivity} cuando `must_change_password` es true (un admin
 * le reseteó la contraseña): en ese caso, si el operador vuelve atrás sin
 * cambiarla, PrincipalActivity vuelve a abrir esta pantalla.
 */
public class CambiarPasswordActivity extends AppCompatActivity {

    public static final String EXTRA_OBLIGATORIO = "obligatorio";

    private static final String TAG = "CambiarPassword";

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

        botonCambiar.setOnClickListener(v -> onCambiarClick());
    }

    private void onCambiarClick() {
        String actual = editPasswordActual.getText().toString();
        String nueva = editPasswordNueva.getText().toString();
        if (actual.isEmpty() || nueva.isEmpty()) {
            Toast.makeText(this, "Completá los dos campos", Toast.LENGTH_SHORT).show();
            return;
        }

        botonCambiar.setEnabled(false);
        botonCambiar.setText("Cambiando...");
        new Thread(() -> {
            try {
                JSONObject cuerpo = new JSONObject().put("current_password", actual).put("new_password", nueva);
                HttpCliente.Respuesta respuesta = HttpCliente.postAutenticado(this, Config.BASE_URL + "/api/core/users/me/cambiar-password/", cuerpo);
                if (respuesta.esExitosa()) {
                    runOnUiThread(() -> {
                        Toast.makeText(this, "Contraseña actualizada", Toast.LENGTH_SHORT).show();
                        finish();
                    });
                    return;
                }
                String mensaje = HttpCliente.mensajeDeError(respuesta.cuerpo, "No se pudo cambiar la contraseña");
                runOnUiThread(() -> Toast.makeText(this, mensaje, Toast.LENGTH_LONG).show());
            } catch (Exception e) {
                Log.e(TAG, "Error cambiando la contraseña", e);
                runOnUiThread(() -> Toast.makeText(this, "No se pudo conectar con el servidor", Toast.LENGTH_SHORT).show());
            }
            runOnUiThread(() -> {
                botonCambiar.setEnabled(true);
                botonCambiar.setText(R.string.password_boton_cambiar);
            });
        }).start();
    }
}
