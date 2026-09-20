package com.udc.operador;

import android.os.Bundle;
import android.widget.ListView;
import android.widget.TextView;

/**
 * Conversaciones cerradas del operador (`?bandeja=cerradas`). Solo lectura:
 * tocar una la abre sin poder responder, cerrar, etiquetar ni derivar (Core
 * no permite reabrirlas todavía).
 */
public class CerradasActivity extends ActividadBase {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_cerradas);
        setTitle(R.string.cerradas_titulo);
        getSupportActionBar().setDisplayHomeAsUpEnabled(true);

        // Con 401 se vuelve a la pantalla principal, que es la que manda al login.
        ListaConversaciones lista = new ListaConversaciones(this, (ListView) findViewById(R.id.listaCerradas),
                findViewById(R.id.progresoCerradas), (TextView) findViewById(R.id.textSinCerradas), true, this::finish);
        lista.cargar("cerradas");
    }
}
