import hmac
from fastapi import Header, HTTPException, status
from app.config import settings

def verify_service_token(authorization: str = Header(..., alias="Authorization")):
    """
    Valida que la petición interna provenga de Core verificando el encabezado:
    Authorization: Service-Token <CORE_SERVICE_TOKEN>
    Utiliza hmac.compare_digest para prevenir ataques de temporización (timing attacks).
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta encabezado de autorización"
        )
    
    parts = authorization.strip().split(" ")
    if len(parts) != 2 or parts[0] != "Service-Token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Formato de autorización inválido. Se espera: Service-Token <token>"
        )
    
    token_recibido = parts[1]
    if not settings.CORE_SERVICE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CORE_SERVICE_TOKEN no está configurado en el servicio Webchat"
        )
    
    # Comparación segura de tiempo constante
    if not hmac.compare_digest(token_recibido, settings.CORE_SERVICE_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service token inválido"
        )
    
    return True
