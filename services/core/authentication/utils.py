def get_client_ip(request) -> str:
    """IP real del cliente. nginx corre como proxy delante de gunicorn
    (services/core/docker/nginx.conf), así que `REMOTE_ADDR` es la IP de
    nginx, no la del usuario — hay que leerla de `X-Forwarded-For` (que
    nginx sí completa con `$proxy_add_x_forwarded_for`)."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")
