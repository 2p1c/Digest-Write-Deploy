#!/usr/bin/env bash

set -euo pipefail

SERVICES=(summary site_maintainer feishu_doc)
HEALTH_PATH="${HEALTH_PATH:-/health}"

port_for_service() {
  case "$1" in
    summary) echo "8001" ;;
    site_maintainer) echo "8002" ;;
    feishu_doc) echo "8003" ;;
    *) return 1 ;;
  esac
}

echo "[1/3] Checking required services are running..."
for svc in "${SERVICES[@]}"; do
  if ! docker compose ps --services --status running | grep -q "^${svc}$"; then
    echo "ERROR: service '${svc}' is not running."
    echo "Start stack first: docker compose up -d --build"
    exit 1
  fi
done
echo "OK: all services are running."

echo "[2/3] Checking host -> container health endpoints..."
for svc in "${SERVICES[@]}"; do
  port="$(port_for_service "$svc")"
  url="http://127.0.0.1:${port}${HEALTH_PATH}"
  if curl -fsS --max-time 5 "$url" >/dev/null; then
    echo "OK: ${svc} health check passed at ${url}"
  else
    echo "ERROR: ${svc} health check failed at ${url}"
    exit 1
  fi
done

echo "[3/3] Checking container-to-container communication..."
for src in "${SERVICES[@]}"; do
  for dst in "${SERVICES[@]}"; do
    url="http://${dst}:8000${HEALTH_PATH}"
    if docker compose exec -T "$src" bash -lc "curl -fsS --max-time 5 '$url' >/dev/null"; then
      echo "OK: ${src} -> ${dst} reachable (${url})"
    else
      echo "ERROR: ${src} cannot reach ${dst} (${url})"
      exit 1
    fi
  done
done

echo "All checks passed: 3 services are healthy and can communicate with each other."
