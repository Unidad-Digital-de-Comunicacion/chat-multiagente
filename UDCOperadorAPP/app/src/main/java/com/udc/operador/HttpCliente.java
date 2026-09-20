package com.udc.operador;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.util.concurrent.TimeUnit;

import okhttp3.Interceptor;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import okhttp3.ResponseBody;
import okhttp3.Route;
import retrofit2.Call;
import retrofit2.Retrofit;

/**
 * La conexión con Core: un cliente Retrofit ({@link #api}) que agrega el token
 * de {@link Sesion} a cada pedido y, si Core contesta 401 porque el token
 * venció, pide uno nuevo con el refresh y reintenta una vez (contrato §1).
 * Si el refresh también venció, el 401 llega a la pantalla, que decide mandar
 * al login. Hay que llamarlo desde un hilo de background
 * (ver {@link ActividadBase#enSegundoPlano}).
 */
public class HttpCliente {

    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");
    private static final Object CERROJO_RENOVACION = new Object();

    private static ApiCore api;

    /** Resultado de un pedido: el código HTTP y el texto de la respuesta. */
    public static class Respuesta {
        public final int codigo;
        public final String cuerpo;

        Respuesta(int codigo, String cuerpo) {
            this.codigo = codigo;
            this.cuerpo = cuerpo;
        }

        public boolean esExitosa() {
            return codigo >= 200 && codigo < 300;
        }
    }

    public static synchronized ApiCore api() {
        if (api == null) {
            OkHttpClient cliente = new OkHttpClient.Builder()
                    .readTimeout(30, TimeUnit.SECONDS) // responder espera a que Channel Gateway entregue el mensaje
                    .addInterceptor(HttpCliente::agregarToken)
                    .authenticator(HttpCliente::renovarYReintentar)
                    .build();
            api = new Retrofit.Builder().baseUrl(Config.BASE_URL + "/").client(cliente).build().create(ApiCore.class);
        }
        return api;
    }

    /** Ejecuta un pedido de {@link ApiCore} y devuelve el código y el texto de la respuesta (también si fue un error). */
    public static Respuesta ejecutar(Call<ResponseBody> llamada) throws IOException {
        retrofit2.Response<ResponseBody> respuesta = llamada.execute();
        ResponseBody cuerpo = respuesta.isSuccessful() ? respuesta.body() : respuesta.errorBody();
        return new Respuesta(respuesta.code(), cuerpo == null ? "" : cuerpo.string());
    }

    /** El cuerpo JSON de un pedido. */
    public static RequestBody json(JSONObject objeto) {
        return RequestBody.create(objeto.toString(), JSON);
    }

    /**
     * Mensaje legible de una respuesta de error de la API (contrato §5):
     * `error.detail` — string directo, lista `["msg", ...]` (error que no es
     * de un campo puntual) o `{"campo": ["msg", ...]}` para errores de
     * validación (en ambos casos se usa el primer mensaje).
     */
    public static String mensajeDeError(String cuerpo, String porDefecto) {
        try {
            JSONObject json = new JSONObject(cuerpo);
            Object detalle = json.getJSONObject("error").get("detail");
            if (detalle instanceof JSONObject) {
                JSONObject campos = (JSONObject) detalle;
                Object valor = campos.get(campos.keys().next());
                return valor instanceof JSONArray ? ((JSONArray) valor).getString(0) : valor.toString();
            }
            if (detalle instanceof JSONArray) {
                return ((JSONArray) detalle).getString(0);
            }
            return detalle.toString();
        } catch (Exception e) {
            return porDefecto;
        }
    }

    // --- Token de acceso ---

    /** Los pedidos de `api/auth/` (login y refresh) van sin token: uno vencido haría fallar hasta el refresh. */
    private static boolean esDeAutenticacion(Request pedido) {
        return pedido.url().encodedPath().startsWith("/api/auth/");
    }

    private static Response agregarToken(Interceptor.Chain cadena) throws IOException {
        Request pedido = cadena.request();
        String access = Sesion.obtenerAccess(App.contexto());
        if (access != null && !esDeAutenticacion(pedido)) {
            pedido = pedido.newBuilder().header("Authorization", "Bearer " + access).build();
        }
        return cadena.proceed(pedido);
    }

    /** OkHttp llama a esto cuando Core contesta 401: devuelve el pedido con el token nuevo, o null para rendirse. */
    private static Request renovarYReintentar(Route ruta, Response respuesta) {
        String usado = respuesta.request().header("Authorization");
        if (usado == null || esDeAutenticacion(respuesta.request()) || respuesta.priorResponse() != null) {
            return null;
        }
        synchronized (CERROJO_RENOVACION) {
            // Si otro pedido ya renovó el token mientras este esperaba, alcanza con reintentar con el nuevo.
            if (usado.equals("Bearer " + Sesion.obtenerAccess(App.contexto())) && !renovarAccess()) {
                return null;
            }
            return respuesta.request().newBuilder()
                    .header("Authorization", "Bearer " + Sesion.obtenerAccess(App.contexto()))
                    .build();
        }
    }

    /** Pide un access nuevo con el refresh guardado. false si el refresh también venció. */
    public static boolean renovarAccess() {
        String refresh = Sesion.obtenerRefresh(App.contexto());
        if (refresh == null) {
            return false;
        }
        try {
            Respuesta respuesta = ejecutar(api().renovarToken(json(new JSONObject().put("refresh", refresh))));
            if (!respuesta.esExitosa()) {
                return false;
            }
            Sesion.guardarAccess(App.contexto(), new JSONObject(respuesta.cuerpo).getString("access"));
            return true;
        } catch (Exception e) {
            return false;
        }
    }
}
