#!/usr/bin/env bash
# Intention: manage the local Redpanda, RustFS, ClickHouse, and PostgreSQL stack.
# Expected result: config validates, or the requested lifecycle action completes.
# Safety: up/down preserve named volumes; reset is destructive and requires confirmation.
# Usage: ./scripts/local-stack.sh config|build|up|restart|down|ps|logs|reset [service]
# Failure: missing runtime, invalid config, unhealthy service, or missing reset confirmation.
# Evidence: prints runtime, action, service status, and safe command output only.

set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT/deploy/local/compose.yaml"
ENV_FILE="${LOCAL_STACK_ENV_FILE:-$ROOT/deploy/local/.env.example}"
ACTION="${1:-config}"
SERVICE="${2:-}"

if [[ ! -f "$COMPOSE_FILE" || ! -f "$ENV_FILE" ]]; then
    printf 'ERROR local stack definition or environment template is missing\n' >&2
    exit 1
fi

if docker compose version >/dev/null 2>&1; then
    RUNTIME=(docker compose)
elif podman compose version >/dev/null 2>&1; then
    RUNTIME=(podman compose)
elif command -v podman-compose >/dev/null 2>&1 && podman-compose version >/dev/null 2>&1; then
    RUNTIME=(podman-compose)
else
    printf 'ERROR no supported Docker Compose or Podman Compose runtime found\n' >&2
    exit 1
fi

printf 'runtime=%s\n' "${RUNTIME[*]}"

case "$ACTION" in
    config)
        "${RUNTIME[@]}" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" --project-name high-vol-ingestor config --quiet
        printf 'action=config result=passed\n'
        ;;
    build)
        "${RUNTIME[@]}" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" --project-name high-vol-ingestor build
        printf 'action=build result=passed\n'
        ;;
    up)
        if [[ -n "$SERVICE" ]]; then
            "${RUNTIME[@]}" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" --project-name high-vol-ingestor up -d "$SERVICE"
        else
            "${RUNTIME[@]}" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" --project-name high-vol-ingestor up -d
        fi
        ;;
    restart)
        if [[ -z "$SERVICE" ]]; then
            printf 'ERROR restart requires a service name\n' >&2
            exit 1
        fi
        "${RUNTIME[@]}" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" --project-name high-vol-ingestor up -d --force-recreate "$SERVICE"
        ;;
    down)
        if [[ -n "$SERVICE" ]]; then
            "${RUNTIME[@]}" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" --project-name high-vol-ingestor down "$SERVICE"
        else
            "${RUNTIME[@]}" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" --project-name high-vol-ingestor down
        fi
        ;;
    ps)
        "${RUNTIME[@]}" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" --project-name high-vol-ingestor ps
        ;;
    logs)
        if [[ -n "$SERVICE" ]]; then
            "${RUNTIME[@]}" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" --project-name high-vol-ingestor logs "$SERVICE"
        else
            "${RUNTIME[@]}" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" --project-name high-vol-ingestor logs
        fi
        ;;
    reset)
        if [[ "${CONFIRM_LOCAL_RESET:-}" != "YES" ]]; then
            printf 'ERROR reset requires CONFIRM_LOCAL_RESET=YES\n' >&2
            exit 1
        fi
        "${RUNTIME[@]}" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" --project-name high-vol-ingestor down --volumes
        ;;
    *)
        printf 'ERROR unknown action: %s\n' "$ACTION" >&2
        exit 1
        ;;
esac
