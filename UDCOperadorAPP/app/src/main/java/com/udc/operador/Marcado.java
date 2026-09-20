package com.udc.operador;

import android.graphics.Typeface;
import android.text.SpannableStringBuilder;
import android.text.Spanned;
import android.text.style.StrikethroughSpan;
import android.text.style.StyleSpan;
import android.text.style.TypefaceSpan;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Convierte el marcado neutro del proyecto (docs/CONTEXTO_PROYECTO.md §4.1.2)
 * en texto con estilo: `**negrita**`, `_cursiva_`, `~tachado~` y
 * `` `monoespaciado` ``. Las negritas, cursivas y tachados se pueden anidar
 * (`**negrita y _cursiva_**`). Lo que no cierra bien queda como texto plano.
 */
public class Marcado {

    // Cursiva y tachado exigen que el símbolo no esté pegado a una letra (para no tocar "foo_bar_baz").
    private static final Pattern PATRON = Pattern.compile(
            "\\*\\*(?=\\S)(.+?)(?<=\\S)\\*\\*"        // 1: negrita
            + "|(?<!\\w)_(?=\\S)(.+?)(?<=\\S)_(?!\\w)" // 2: cursiva
            + "|(?<!\\w)~(?=\\S)(.+?)(?<=\\S)~(?!\\w)" // 3: tachado
            + "|`(.+?)`");                             // 4: monoespaciado

    public static SpannableStringBuilder aplicar(String texto) {
        SpannableStringBuilder resultado = new SpannableStringBuilder();
        Matcher coincidencia = PATRON.matcher(texto);
        int desde = 0;
        while (coincidencia.find()) {
            resultado.append(texto, desde, coincidencia.start());
            for (int grupo = 1; grupo <= 4; grupo++) {
                String contenido = coincidencia.group(grupo);
                if (contenido != null) {
                    int inicio = resultado.length();
                    // El monoespaciado es texto literal; los demás pueden llevar otros estilos adentro.
                    resultado.append(grupo == 4 ? contenido : aplicar(contenido));
                    resultado.setSpan(estilo(grupo), inicio, resultado.length(), Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                    break;
                }
            }
            desde = coincidencia.end();
        }
        resultado.append(texto, desde, texto.length());
        return resultado;
    }

    private static Object estilo(int grupo) {
        switch (grupo) {
            case 1:
                return new StyleSpan(Typeface.BOLD);
            case 2:
                return new StyleSpan(Typeface.ITALIC);
            case 3:
                return new StrikethroughSpan();
            default:
                return new TypefaceSpan("monospace");
        }
    }
}
