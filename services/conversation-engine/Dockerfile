FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==26.2.2 \
    && pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# gunicorn supervisa el proceso (lo reinicia si se cuelga) en vez de un
# `uvicorn` suelto sin supervisión — sin nginx delante: Cloudflare Tunnel ya
# termina TLS y apunta directo a este puerto, y `UvicornWorker` soporta
# WebSocket igual que uvicorn solo (`WS /ws/operador/{token}`).
# A PROPÓSITO 1 solo worker, no varios: `connections.GestorConexiones` es un
# diccionario en memoria de proceso, sin backing compartido (Redis queda
# afuera por restricción del proyecto) — con 2+ workers, un operador
# conectado al worker A nunca se entera de un evento que gunicorn le rutea
# al worker B. Si hace falta escalar esto de verdad más adelante, hay que
# resolver primero el registro compartido, no subir el número acá.
CMD ["gunicorn", "app.main:app", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "1"]
