package com.udc.operador;

import static com.udc.operador.HttpCliente.api;
import static com.udc.operador.HttpCliente.ejecutar;
import static com.udc.operador.HttpCliente.json;

import android.content.Intent;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;

import org.json.JSONObject;

/**
 * La sección "Perfil" de la pantalla principal: el email del usuario, editar
 * nombre/apellido/DNI (PATCH /api/core/users/me/) y los botones de cambiar
 * contraseña y cerrar sesión (contrato §1).
 */
public class PerfilSeccion {

    private final ActividadBase actividad;
    private final Runnable alCerrarSesion;
    private final TextView textEmail;
    private final EditText editNombre;
    private final EditText editApellido;
    private final EditText editDni;
    private final Button botonGuardar;

    /** `alCerrarSesion` corre en el hilo principal: con el botón "Cerrar sesión" o si Core contesta 401. */
    public PerfilSeccion(ActividadBase actividad, View raiz, Runnable alCerrarSesion) {
        this.actividad = actividad;
        this.alCerrarSesion = alCerrarSesion;
        textEmail = raiz.findViewById(R.id.textEmail);
        editNombre = raiz.findViewById(R.id.editNombre);
        editApellido = raiz.findViewById(R.id.editApellido);
        editDni = raiz.findViewById(R.id.editDni);
        botonGuardar = raiz.findViewById(R.id.botonGuardarPerfil);

        botonGuardar.setOnClickListener(v -> guardar());
        raiz.findViewById(R.id.botonCambiarPassword).setOnClickListener(v ->
                actividad.startActivity(new Intent(actividad, CambiarPasswordActivity.class)));
        raiz.findViewById(R.id.botonCerrarSesion).setOnClickListener(v -> alCerrarSesion.run());
    }

    /** Además de llenar la pantalla, dice si hay que cambiar la contraseña (`must_change_password`). */
    public void cargar() {
        actividad.enSegundoPlano(() -> {
            HttpCliente.Respuesta respuesta = ejecutar(api().perfil());
            if (respuesta.codigo == 401) {
                actividad.runOnUiThread(alCerrarSesion);
                return;
            }
            if (!respuesta.esExitosa()) {
                actividad.avisar("No se pudo cargar el perfil");
                return;
            }
            JSONObject perfil = new JSONObject(respuesta.cuerpo);
            actividad.runOnUiThread(() -> mostrar(perfil));
        });
    }

    private void mostrar(JSONObject perfil) {
        textEmail.setText(perfil.optString("email"));
        editNombre.setText(texto(perfil, "first_name"));
        editApellido.setText(texto(perfil, "last_name"));
        editDni.setText(texto(perfil, "dni"));

        // Un admin le reseteó la contraseña: no puede seguir sin cambiarla.
        if (perfil.optBoolean("must_change_password")) {
            Intent intent = new Intent(actividad, CambiarPasswordActivity.class);
            intent.putExtra(CambiarPasswordActivity.EXTRA_OBLIGATORIO, true);
            actividad.startActivity(intent);
        }
    }

    /** Un campo que puede venir null en el JSON (ej. `dni`) se muestra vacío, no como "null". */
    private static String texto(JSONObject json, String campo) {
        return json.isNull(campo) ? "" : json.optString(campo);
    }

    private void guardar() {
        String nombre = editNombre.getText().toString().trim();
        String apellido = editApellido.getText().toString().trim();
        String dni = editDni.getText().toString().trim();

        actividad.enSegundoPlanoBloqueando(botonGuardar, "Guardando...", () -> {
            HttpCliente.Respuesta respuesta = ejecutar(api().guardarPerfil(
                    json(new JSONObject().put("first_name", nombre).put("last_name", apellido).put("dni", dni))));
            if (respuesta.codigo == 401) {
                actividad.runOnUiThread(alCerrarSesion);
                return;
            }
            actividad.avisar(respuesta.esExitosa()
                    ? "Perfil actualizado"
                    : HttpCliente.mensajeDeError(respuesta.cuerpo, "No se pudo guardar el perfil"));
        });
    }
}
