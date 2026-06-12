# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.11
ARG NODE_VERSION=22

FROM python:${PYTHON_VERSION}-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SEO_STUDIO_ENVIRONMENT=production \
    SEO_STUDIO_STORAGE_ROOT=/app/storage

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend/app ./app

RUN mkdir -p /app/storage/uploads /app/storage/processed /app/storage/exports /app/storage/temp \
    && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM node:${NODE_VERSION}-alpine AS frontend-deps

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM node:${NODE_VERSION}-alpine AS frontend-builder

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

COPY --from=frontend-deps /app/node_modules ./node_modules
COPY frontend/ ./
RUN npm run build

FROM node:${NODE_VERSION}-alpine AS frontend

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

RUN addgroup -S app && adduser -S -G app app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY --from=frontend-builder /app/.next ./.next
COPY --from=frontend-builder /app/public ./public

RUN chown -R app:app /app

USER app

EXPOSE 3000

CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
