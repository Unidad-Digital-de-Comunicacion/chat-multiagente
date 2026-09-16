package com.udc.operador;

/**
 * Un solo lugar para la URL base de Core, para no repetirla en cada
 * Activity (ver AGENTS.md, sección "Red"). Apunta al servidor real, así no
 * hace falta tener Core corriendo en local (docker compose) para probar la
 * app — para desarrollar contra un Core local, cambiar esto por
 * "http://10.0.2.2:8001" (emulador) o la IP LAN de la PC (celular físico).
 */
public class Config {
    public static final String BASE_URL = "https://api.udcchat.com.ar";
}
