FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1

# nginx: sirve /static y /media y hace de proxy a gunicorn (127.0.0.1:8000,
# no expuesto fuera del contenedor). supervisor: mantiene arriba a los dos
# procesos dentro del mismo contenedor. curl: usado por el healthcheck.
RUN apt-get update \
    && apt-get install --no-install-recommends -y nginx supervisor curl libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN rm -f /etc/nginx/sites-enabled/default \
    && cp docker/nginx.conf /etc/nginx/conf.d/core.conf \
    && mkdir -p /etc/supervisor/conf.d \
    && cp docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf \
    && mkdir -p /app/staticfiles /app/mediafiles /app/keys \
    && chmod +x entrypoint.sh

EXPOSE 80

ENTRYPOINT ["./entrypoint.sh"]
