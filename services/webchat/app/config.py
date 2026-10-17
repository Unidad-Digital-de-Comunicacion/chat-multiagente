import os

class Settings:
    # URL base del servicio Core (Django). "CORE_BASE_URL" (no "CORE_URL")
    # porque es el nombre que ya inyecta `x-fastapi-common` en
    # docker-compose.yml para todos los microservicios FastAPI del
    # monorepo — y el puerto real adentro del contenedor de Core es el 80
    # (nginx + gunicorn vía supervisord), no el 8000 que usan los stubs
    # FastAPI.
    CORE_URL: str = os.getenv("CORE_BASE_URL", "http://core:80")

    # Token de autenticación de servicio compartido con Core
    CORE_SERVICE_TOKEN: str = os.getenv("CORE_SERVICE_TOKEN", "")
    
    # Orígenes permitidos para CORS (por ser widget embebible en sitios de terceros, por defecto "*")
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")
    
    # Puerto del servicio
    PORT: int = int(os.getenv("PORT", "8006"))

settings = Settings()
