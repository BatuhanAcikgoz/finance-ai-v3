#!/usr/bin/env bash
# =============================================================================
# Wait for the docker stack to be ready.
# =============================================================================
# Polls Postgres/Redis/Qdrant via docker exec + the api-gateway HTTP /health.
# Exits 0 on success, 1 on timeout (default 120s).
# =============================================================================

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-infra/docker/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-infra/docker/.env.docker}"
TIMEOUT="${TIMEOUT:-120}"
HOST_PORT="${API_GATEWAY_PORT:-8000}"
BASE_URL="http://localhost:${HOST_PORT}"

# shellcheck disable=SC2046
DOCKER_COMPOSE=(docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE")

elapsed=0
log() { printf '[wait_for %4ds] %s\n' "$elapsed" "$*"; }

wait_http() {
    local url="$1" name="$2"
    local code
    code="$(curl -s -o /dev/null -w '%{http_code}' "$url" || true)"
    [[ "$code" == "200" ]]
}

log "Polling ${BASE_URL}/health (timeout ${TIMEOUT}s)…"

while (( elapsed < TIMEOUT )); do
    if wait_http "${BASE_URL}/health" "api-gateway"; then
        log "api-gateway is up."
        log "Polling infra deps…"

        # Postgres
        if "${DOCKER_COMPOSE[@]}" exec -T postgres pg_isready -U "${POSTGRES_USER:-finance_ai_v3}" >/dev/null 2>&1; then
            log "postgres: ready"
        else
            log "postgres: not ready yet"
            sleep 5; elapsed=$((elapsed+5)); continue
        fi

        # Redis
        if "${DOCKER_COMPOSE[@]}" exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
            log "redis: ready"
        else
            log "redis: not ready yet"
            sleep 5; elapsed=$((elapsed+5)); continue
        fi

        # Qdrant
        if wait_http "http://localhost:6333/health" "qdrant"; then
            log "qdrant: ready"
        else
            log "qdrant: not ready yet"
            sleep 5; elapsed=$((elapsed+5)); continue
        fi

        log "All services ready."
        exit 0
    fi
    sleep 3
    elapsed=$((elapsed+3))
done

log "Timeout (${TIMEOUT}s) waiting for stack."
log "Hints: docker compose -f $COMPOSE_FILE --env-file $ENV_FILE ps"
log "       docker compose -f $COMPOSE_FILE --env-file $ENV_FILE logs --tail=200 api-gateway"
exit 1
