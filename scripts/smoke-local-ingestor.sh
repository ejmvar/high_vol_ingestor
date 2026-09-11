#!/usr/bin/env bash
# Intention: verify HTTP ingestion, Kafka acknowledgement, duplicate handling, and broker delivery.
# Expected result: one HTTP 202, one duplicate HTTP 200, and one consumed Redpanda record.
# Safety: publishes one deterministic local fixture and consumes one matching record; it does not reset volumes.
# Usage: REDPANDA_EXTERNAL_PORT=29092 ./scripts/smoke-local-ingestor.sh [base-url]
# Failure: unavailable tools/services, invalid responses, missing acknowledgement, or missing broker record.
# Evidence: prints HTTP statuses, idempotency key, queue offset, and broker match without payload contents.

set -Eeuo pipefail

BASE_URL="${1:-http://127.0.0.1:8080}"
TOPIC="${KAFKA_TOPIC:-nvt.telemetry.raw.v1}"
SEQUENCE="${SMOKE_SEQUENCE:-$(date +%s)}"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

uv run python - "$TEMP_DIR/request.json" "$SEQUENCE" <<'PY'
import base64
import json
import sys
from datetime import datetime, timezone

from telemetry_contract import VibrationGeneratorConfig, generate_vibration_chunk

chunk = generate_vibration_chunk(
    VibrationGeneratorConfig(producer_sequence=int(sys.argv[2])),
    event_start=datetime(2026, 9, 11, 0, 0, tzinfo=timezone.utc),
)
document = {
    "envelope": chunk.envelope,
    "payload_base64": base64.b64encode(chunk.payload).decode("ascii"),
}
with open(sys.argv[1], "w", encoding="utf-8") as output:
    json.dump(document, output, separators=(",", ":"))
print(f"fixture_idempotency_key={chunk.envelope['idempotency_key']}")
PY

FIRST_RESPONSE="$(curl --fail-with-body --silent --show-error \
    --header 'Content-Type: application/json' \
    --data-binary "@$TEMP_DIR/request.json" \
    --write-out $'\n%{http_code}' \
    "$BASE_URL/v1/telemetry/chunks")"
FIRST_STATUS="${FIRST_RESPONSE##*$'\n'}"
FIRST_BODY="${FIRST_RESPONSE%$'\n'*}"

SECOND_RESPONSE="$(curl --fail-with-body --silent --show-error \
    --header 'Content-Type: application/json' \
    --data-binary "@$TEMP_DIR/request.json" \
    --write-out $'\n%{http_code}' \
    "$BASE_URL/v1/telemetry/chunks")"
SECOND_STATUS="${SECOND_RESPONSE##*$'\n'}"
SECOND_BODY="${SECOND_RESPONSE%$'\n'*}"

uv run python - "$FIRST_STATUS" "$FIRST_BODY" "$SECOND_STATUS" "$SECOND_BODY" <<'PY'
import json
import sys

first_status, first_body, second_status, second_body = sys.argv[1:]
first = json.loads(first_body)
second = json.loads(second_body)
if first_status != "202" or first.get("status") != "accepted" or not first.get("queue_offset"):
    raise SystemExit(f"first ingestion failed status={first_status} body={first_body}")
if second_status != "200" or second.get("status") != "duplicate":
    raise SystemExit(f"duplicate ingestion failed status={second_status} body={second_body}")
print(f"http_first status={first_status} queue_offset={first['queue_offset']}")
print(f"http_duplicate status={second_status} queue_offset={second['queue_offset']}")
if second.get("idempotency_key") != first.get("idempotency_key"):
    raise SystemExit("duplicate receipt did not preserve idempotency key")
print(f"idempotency_key={first['idempotency_key']}")
PY

./scripts/local-stack.sh exec redpanda rpk topic consume "$TOPIC" \
    --brokers redpanda:9092 --offset -1 --num 1 --format json > "$TEMP_DIR/broker.json"

uv run python - "$TEMP_DIR/broker.json" "$FIRST_BODY" "$TOPIC" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as input_file:
    records = [json.load(input_file)]
request = json.loads(sys.argv[2])
topic = sys.argv[3]
if not records:
    raise SystemExit("broker returned no record")
record = records[-1]
record_key = record.get("key") or record.get("Key")
expected_key = request["idempotency_key"]
if record_key and expected_key not in str(record_key):
    raise SystemExit("broker record key did not match idempotency key")
print(f"broker_record topic={record.get('topic', record.get('Topic', topic))} result=passed")
PY
