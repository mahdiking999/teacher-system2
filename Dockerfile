# Stage 1: Build Next.js Frontend (Standalone)
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
ENV NODE_OPTIONS="--max-old-space-size=400"
ENV INTERNAL_API_URL="http://127.0.0.1:8000"
ENV NEXT_PUBLIC_API_BASE_URL=""
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN mkdir -p /app/frontend/public && npm run build

# Stage 2: Unified Runtime (Python FastAPI + Node.js Standalone)
FROM python:3.12-slim AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends nodejs ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=tailscale/tailscale:stable /usr/local/bin/tailscaled /usr/local/bin/tailscaled
COPY --from=tailscale/tailscale:stable /usr/local/bin/tailscale /usr/local/bin/tailscale

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir fastapi uvicorn SQLAlchemy alembic pydantic pydantic-settings python-multipart python-dotenv psycopg2-binary httpx "pymupdf>=1.25.0,<2.0"

COPY backend/ ./backend/
COPY scripts/start_prod.sh ./scripts/start_prod.sh
RUN sed -i 's/\r$//' ./scripts/start_prod.sh && chmod +x ./scripts/start_prod.sh

COPY --from=frontend-builder /app/frontend/.next/standalone ./frontend/
COPY --from=frontend-builder /app/frontend/.next/static ./frontend/.next/static
COPY --from=frontend-builder /app/frontend/public ./frontend/public

ENV DATA_DIR="/app/data"
ENV STORAGE_ROOT="/app/backend/storage"
ENV ENABLE_DEMO_SEED="1"
ENV INTERNAL_API_URL="http://127.0.0.1:8000"
ENV PORT="10000"

EXPOSE 10000
CMD ["/app/scripts/start_prod.sh"]
