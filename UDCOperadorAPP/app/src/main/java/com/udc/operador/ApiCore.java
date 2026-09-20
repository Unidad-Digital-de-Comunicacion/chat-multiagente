package com.udc.operador;

import okhttp3.RequestBody;
import okhttp3.ResponseBody;
import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.DELETE;
import retrofit2.http.GET;
import retrofit2.http.PATCH;
import retrofit2.http.POST;
import retrofit2.http.Path;
import retrofit2.http.Query;

/**
 * Todos los endpoints de Core que usa la app (docs/operators-desk-api-contract.md),
 * un método por cada uno. Devuelven el cuerpo crudo: se ejecutan con
 * {@link HttpCliente#ejecutar} y el JSON se lee con org.json. Los cuerpos se
 * arman con {@link HttpCliente#json}. El token de acceso lo agrega
 * {@link HttpCliente} solo, a todos menos a los de `api/auth/`.
 */
public interface ApiCore {

    // --- Sesión (sin token) ---

    @POST("api/auth/login/")
    Call<ResponseBody> login(@Body RequestBody credenciales);

    @POST("api/auth/refresh/")
    Call<ResponseBody> renovarToken(@Body RequestBody refresh);

    // --- Perfil ---

    @GET("api/core/users/me/")
    Call<ResponseBody> perfil();

    @PATCH("api/core/users/me/")
    Call<ResponseBody> guardarPerfil(@Body RequestBody datos);

    @POST("api/core/users/me/cambiar-password/")
    Call<ResponseBody> cambiarPassword(@Body RequestBody contrasenas);

    // --- Catálogos de la organización ---

    @GET("api/core/etiquetas/")
    Call<ResponseBody> etiquetas();

    @GET("api/core/teams/")
    Call<ResponseBody> equipos();

    // --- Conversaciones ---

    /** `bandeja`: sin_asignar, mias o cerradas. Core devuelve de a 25 (`pagina` empieza en 1). */
    @GET("api/core/conversaciones/")
    Call<ResponseBody> conversaciones(@Query("bandeja") String bandeja, @Query("page") int pagina);

    @POST("api/core/conversaciones/{id}/tomar/")
    Call<ResponseBody> tomar(@Path("id") int id);

    @GET("api/core/conversaciones/{id}/mensajes/")
    Call<ResponseBody> mensajes(@Path("id") int id);

    @POST("api/core/conversaciones/{id}/responder/")
    Call<ResponseBody> responder(@Path("id") int id, @Body RequestBody mensaje);

    @POST("api/core/conversaciones/{id}/cerrar/")
    Call<ResponseBody> cerrar(@Path("id") int id);

    @POST("api/core/conversaciones/{id}/derivar/")
    Call<ResponseBody> derivar(@Path("id") int id, @Body RequestBody destino);

    @GET("api/core/conversaciones/{id}/etiquetas/")
    Call<ResponseBody> etiquetasDe(@Path("id") int id);

    @POST("api/core/conversaciones/{id}/etiquetas/")
    Call<ResponseBody> aplicarEtiqueta(@Path("id") int id, @Body RequestBody etiqueta);

    @DELETE("api/core/conversaciones/{id}/etiquetas/{etiquetaId}/")
    Call<ResponseBody> quitarEtiqueta(@Path("id") int id, @Path("etiquetaId") int etiquetaId);

    @GET("api/core/conversaciones/{id}/observaciones/")
    Call<ResponseBody> observaciones(@Path("id") int id);

    @GET("api/core/conversaciones/{id}/notas-internas/")
    Call<ResponseBody> notas(@Path("id") int id);

    @POST("api/core/conversaciones/{id}/notas-internas/")
    Call<ResponseBody> agregarNota(@Path("id") int id, @Body RequestBody nota);
}
