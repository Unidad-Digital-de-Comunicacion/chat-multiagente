package com.udc.operador;

import android.content.Context;
import android.graphics.Color;
import android.text.SpannableStringBuilder;
import android.text.Spanned;
import android.text.style.BackgroundColorSpan;
import android.text.style.ForegroundColorSpan;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.List;

/**
 * Dibuja cada conversación de una lista (GET /api/core/conversaciones/):
 * título, etiquetas con su color y última observación. Lo usan las listas
 * de {@link PrincipalActivity} y de {@link CerradasActivity}.
 */
public class ConversacionesAdapter extends ArrayAdapter<JSONObject> {

    public ConversacionesAdapter(Context context, List<JSONObject> filas) {
        super(context, 0, filas);
    }

    @Override
    public View getView(int posicion, View vista, ViewGroup padre) {
        if (vista == null) {
            vista = LayoutInflater.from(getContext()).inflate(R.layout.item_conversacion, padre, false);
        }
        JSONObject conversacion = getItem(posicion);

        JSONObject contacto = conversacion.optJSONObject("contact");
        String nombre = contacto.optString("nombre");
        String quien = nombre.isEmpty() ? contacto.optString("identificador_externo") : nombre;
        String equipo = conversacion.isNull("team_nombre") ? "sin equipo" : conversacion.optString("team_nombre");
        ((TextView) vista.findViewById(R.id.textFilaTitulo))
                .setText(conversacion.optString("canal_display") + " - " + quien + " (" + equipo + ")");

        TextView textEtiquetas = vista.findViewById(R.id.textFilaEtiquetas);
        SpannableStringBuilder etiquetas = textoDeEtiquetas(conversacion.optJSONArray("etiquetas"));
        textEtiquetas.setText(etiquetas);
        textEtiquetas.setVisibility(etiquetas.length() == 0 ? View.GONE : View.VISIBLE);

        TextView textObservacion = vista.findViewById(R.id.textFilaObservacion);
        JSONObject observacion = conversacion.optJSONObject("ultima_observacion");
        SpannableStringBuilder textoObservacion = new SpannableStringBuilder();
        if (observacion != null) {
            textoObservacion.append("📝 ").append(Marcado.aplicar(observacion.optString("texto")));
        }
        textObservacion.setText(textoObservacion);
        textObservacion.setVisibility(observacion == null ? View.GONE : View.VISIBLE);

        return vista;
    }

    /** Una etiqueta = su nombre con el color de fondo y de letra que manda Core (`color`, `color_texto`). */
    public static SpannableStringBuilder textoDeEtiquetas(JSONArray etiquetas) {
        SpannableStringBuilder texto = new SpannableStringBuilder();
        if (etiquetas == null) {
            return texto;
        }
        for (int i = 0; i < etiquetas.length(); i++) {
            JSONObject etiqueta = etiquetas.optJSONObject(i);
            int inicio = texto.length();
            texto.append(" ").append(etiqueta.optString("nombre")).append(" ");
            texto.setSpan(new BackgroundColorSpan(color(etiqueta.optString("color"), Color.GRAY)),
                    inicio, texto.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            texto.setSpan(new ForegroundColorSpan(color(etiqueta.optString("color_texto"), Color.WHITE)),
                    inicio, texto.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            texto.append("  ");
        }
        return texto;
    }

    private static int color(String hexadecimal, int porDefecto) {
        try {
            return Color.parseColor(hexadecimal);
        } catch (IllegalArgumentException e) {
            return porDefecto;
        }
    }
}
