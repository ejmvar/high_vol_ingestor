#!/usr/bin/env bash
# Intention: verify the local ingestor HTTP readiness endpoint from the host.
# Expected result: the endpoint returns HTTP 200 and the expected JSON status.
# Safety: read-only; it does not publish telemetry or modify service data.
# Usage: ./scripts/verify-local-ingestor.sh [base-url]
# Failure: missing curl, connection failure, non-200 response, or unexpected body.
# Evidence: prints the URL, HTTP status, and secret-free response body.

set -Eeuo pipefail

BASE_URL="${1:-http://127.0.0.1:8080}"
RESPONSE="$(curl --fail-with-body --silent --show-error --write-out $'\n%{http_code}' "$BASE_URL/health")"
STATUS="${RESPONSE##*$'\n'}"
BODY="${RESPONSE%$'\n'*}"

if [[ "$STATUS" != "200" || "$BODY" != '{"status": "ready"}' ]]; then
    printf 'ERROR ingestor health failed url=%s status=%s body=%s\n' "$BASE_URL/health" "$STATUS" "$BODY" >&2
    exit 1
fi

printf 'ingestor_health url=%s status=%s body=%s result=passed\n' "$BASE_URL/health" "$STATUS" "$BODY"
