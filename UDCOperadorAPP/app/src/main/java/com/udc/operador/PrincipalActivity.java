package com.udc.operador;

import android.content.Intent;
import android.os.Bundle;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.widget.TextView;

import com.google.android.material.bottomnavigation.BottomNavigationView;

/**
 * Pantalla principal con menú inferior: conversaciones sin asignar
 * (`?bandeja=sin_asignar`), conversaciones mías (`?bandeja=mias`) y perfil.
 * En "Mías" el menú de los tres puntitos lleva a las cerradas.
 */
public class PrincipalActivity extends ActividadBase {

    // Cada cuánto se refresca la lista mientras la pantalla está a la vista.
    private static final long INTERVALO_SONDEO_MS = 10_000;

    private ListaConversaciones lista;
    private PerfilSeccion perfil;
    private View vistaPerfil;
    private int pantallaActual = R.id.menu_sin_asignar;
    private boolean saliendo;

    private final Sondeo sondeo = new Sondeo(this, INTERVALO_SONDEO_MS, () -> lista.refrescar()).conTiempoReal();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_principal);

        lista = new ListaConversaciones(this, findViewById(R.id.listaConversaciones), findViewById(R.id.progresoLista),
                (TextView) findViewById(R.id.textListaVacia), false, this::cerrarSesion);
        vistaPerfil = findViewById(R.id.vistaPerfil);
        perfil = new PerfilSeccion(this, vistaPerfil, this::cerrarSesion);

        BottomNavigationView menu = findViewById(R.id.menuInferior);
        menu.setOnItemSelectedListener(item -> {
            pantallaActual = item.getItemId();
            lista.reiniciar();
            mostrarPantallaActual();
            return true;
        });
    }

    @Override
    protected void onResume() {
        super.onResume();
        // Recarga al volver (ej. después de tomar o cerrar una conversación).
        perfil.cargar();
        mostrarPantallaActual();
        sondeo.iniciar();
    }

    /** En segundo plano no se sigue consultando. */
    @Override
    protected void onPause() {
        super.onPause();
        sondeo.detener();
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
        vistaPerfil.setVisibility(esPerfil ? View.VISIBLE : View.GONE);
        invalidateOptionsMenu();

        if (esPerfil) {
            lista.ocultar();
        } else {
            lista.setTextoVacio(pantallaActual == R.id.menu_sin_asignar ? R.string.lista_vacia_sin_asignar : R.string.lista_vacia_mias);
            lista.cargar(nombreBandeja());
        }
    }

    private String nombreBandeja() {
        return pantallaActual == R.id.menu_sin_asignar ? "sin_asignar" : "mias";
    }

    /** Varios pedidos a la vez pueden dar 401; el login se abre una sola vez. */
    private void cerrarSesion() {
        if (saliendo) {
            return;
        }
        saliendo = true;
        Sesion.cerrarSesion(this);
        startActivity(new Intent(this, LoginActivity.class));
        finish();
    }
}
