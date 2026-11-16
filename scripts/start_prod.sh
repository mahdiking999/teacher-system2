#!/bin/sh
set -e

mkdir -p "${DATA_DIR:-/app/data}" "${STORAGE_ROOT:-/app/backend/storage}/uploads" "${STORAGE_ROOT:-/app/backend/storage}/exports"

if [ -n "${TAILSCALE_AUTHKEY:-}" ]; then
  echo "[start_prod] Starting Tailscale userspace daemon + HTTP proxy on 127.0.0.1:1055..."
  mkdir -p /tmp/tailscale
  tailscaled --tun=userspace-networking --state=/tmp/tailscale/tailscaled.state --socket=/tmp/tailscale/tailscaled.sock --outbound-http-proxy-listen=127.0.0.1:1055 &
  sleep 2
  if tailscale --socket=/tmp/tailscale/tailscaled.sock up --authkey="${TAILSCALE_AUTHKEY}" --hostname="render-teachersys" --accept-routes; then
    echo "[start_prod] Tailscale connected! Enabling TAILSCALE_HTTP_PROXY=http://127.0.0.1:1055"
    export TAILSCALE_HTTP_PROXY="http://127.0.0.1:1055"
  else
    echo "[start_prod] Warning: tailscale up failed; continuing without Tailscale proxy."
  fi
fi

echo "[start_prod] Starting FastAPI backend on 127.0.0.1:8000..."
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1 &
BACKEND_PID=$!

echo "[start_prod] Waiting for FastAPI readiness at http://127.0.0.1:8000/api/health..."
i=0
while [ $i -lt 30 ]; do
  if python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)" >/dev/null 2>&1; then
    echo "[start_prod] FastAPI is healthy!"
    break
  fi
  i=$((i + 1))
  sleep 1
done

export PORT="${PORT:-10000}"
export HOSTNAME="0.0.0.0"
export INTERNAL_API_URL="http://127.0.0.1:8000"

echo "[start_prod] Starting Next.js standalone server on 0.0.0.0:${PORT}..."
cd /app/frontend
exec node server.js
