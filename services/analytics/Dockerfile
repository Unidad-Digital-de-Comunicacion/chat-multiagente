FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# gunicorn supervisa varios workers de uvicorn (reinicia uno que se cuelgue,
# reparte la carga) en vez de un solo proceso `uvicorn` sin supervisión — sin
# nginx delante: Cloudflare Tunnel ya termina TLS y apunta directo a este
# puerto, no hay estáticos que servir ni beneficio real en sumar una capa
# más (`docker-compose.override.yml` pisa esto con `--reload` en dev).
CMD ["gunicorn", "app.main:app", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "2"]
