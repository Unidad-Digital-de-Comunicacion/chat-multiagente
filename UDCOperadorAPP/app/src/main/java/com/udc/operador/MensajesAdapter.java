package com.udc.operador;

import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.FrameLayout;
import android.widget.TextView;

import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.List;

/**
 * Dibuja el hilo de una conversación como burbujas de chat. El contacto y el
 * sistema (bot) van a la izquierda; los operadores (y las observaciones que
 * cargan) a la derecha. Cada burbuja dice quién habla y cuándo.
 */
public class MensajesAdapter extends ArrayAdapter<MensajesAdapter.Linea> {

    public enum Tipo { CONTACTO, SISTEMA, OPERADOR, OBSERVACION }

    /** Una burbuja: quién (`remitente`), qué (`texto`) y cuándo (`momento`). */
    public static class Linea {
        final Tipo tipo;
        final String remitente;
        final String texto;
        final Instant momento;

        /** `fechaIso` es el `creado_at` que manda Core (con zona horaria, ej. "2026-09-19T18:05:11-03:00"). */
        public Linea(Tipo tipo, String remitente, String texto, String fechaIso) {
            this.tipo = tipo;
            this.remitente = remitente;
            this.texto = texto;
            this.momento = parsear(fechaIso);
        }

        public Instant momento() {
            return momento;
        }

        private static Instant parsear(String fechaIso) {
            try {
                return OffsetDateTime.parse(fechaIso).toInstant();
            } catch (RuntimeException e) {
                return Instant.EPOCH;
            }
        }
    }

    private static final DateTimeFormatter FORMATO_HORA = DateTimeFormatter.ofPattern("dd/MM HH:mm");

    private static final int NEGRO = 0xFF111111;

    public MensajesAdapter(Context context, List<Linea> lineas) {
        super(context, 0, lineas);
    }

    @Override
    public View getView(int posicion, View vista, ViewGroup padre) {
        if (vista == null) {
            vista = LayoutInflater.from(getContext()).inflate(R.layout.item_mensaje, padre, false);
        }
        Linea linea = getItem(posicion);
        boolean aLaDerecha = linea.tipo == Tipo.OPERADOR || linea.tipo == Tipo.OBSERVACION;
        int colorFondo = colorFondo(linea.tipo);
        int colorTexto = linea.tipo == Tipo.OPERADOR ? Color.WHITE : NEGRO;
        float densidad = getContext().getResources().getDisplayMetrics().density;

        View burbuja = vista.findViewById(R.id.burbuja);
        FrameLayout.LayoutParams parametros = (FrameLayout.LayoutParams) burbuja.getLayoutParams();
        parametros.gravity = aLaDerecha ? Gravity.END : Gravity.START;
        // Un margen del lado contrario para que la burbuja no ocupe todo el ancho.
        int margen = (int) (56 * densidad);
        parametros.setMargins(aLaDerecha ? margen : 0, 0, aLaDerecha ? 0 : margen, 0);
        burbuja.setLayoutParams(parametros);

        GradientDrawable fondo = new GradientDrawable();
        fondo.setColor(colorFondo);
        fondo.setCornerRadius(16 * densidad);
        burbuja.setBackground(fondo);

        TextView textRemitente = vista.findViewById(R.id.textRemitente);
        textRemitente.setText(linea.remitente);
        textRemitente.setTextColor(colorTexto);

        TextView textTexto = vista.findViewById(R.id.textTexto);
        textTexto.setText(Marcado.aplicar(linea.texto));
        textTexto.setTextColor(colorTexto);

        TextView textHora = vista.findViewById(R.id.textHora);
        textHora.setText(FORMATO_HORA.format(linea.momento.atZone(ZoneId.systemDefault())));
        textHora.setTextColor(colorTexto);

        return vista;
    }

    private static int colorFondo(Tipo tipo) {
        switch (tipo) {
            case CONTACTO:
                return 0xFFE8E8E8;
            case SISTEMA:
                return 0xFFD6E4FF;
            case OPERADOR:
                return 0xFF6B4FBB;
            default:
                return 0xFFFFF3C4;
        }
    }
}
