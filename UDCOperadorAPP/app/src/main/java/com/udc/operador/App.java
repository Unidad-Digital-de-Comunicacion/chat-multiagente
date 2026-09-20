package com.udc.operador;

import android.app.Application;
import android.content.Context;

/** Guarda el contexto de la aplicación, para que la capa de red pueda leer la sesión sin recibirlo en cada llamada. */
public class App extends Application {

    private static Context contexto;

    @Override
    public void onCreate() {
        super.onCreate();
        contexto = this;
    }

    public static Context contexto() {
        return contexto;
    }
}
