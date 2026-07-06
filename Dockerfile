# Imagem única: builda o frontend (React) e roda a API (FastAPI) servindo o site estático.
# Build:  docker compose build   (ou: docker build -t questpro-web .)

# ---- estágio 1: build do frontend -------------------------------------------------------
FROM node:20-alpine AS fe
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ---- estágio 2: runtime da API ----------------------------------------------------------
FROM python:3.12-slim

# libs de sistema que o opencv-headless costuma pedir em imagens slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=fe /fe/dist ./static

# mídia (frames + mp4) fica num volume montado em /data/media (ver docker-compose.yml)
ENV QUESTPRO_STATIC_DIR=/app/static \
    QUESTPRO_MEDIA_ROOT=/data/media

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
