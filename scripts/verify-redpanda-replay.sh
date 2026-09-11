#!/usr/bin/env bash
# Intention: verify one Redpanda record remains readable after broker restart.
# Expected result: HTTP acceptance, broker restart, and replay from the original offset succeed.
# Safety: publishes one deterministic local fixture and recreates only Redpanda; named volumes are preserved.
# Usage: REDPANDA_EXTERNAL_PORT=29092 ./scripts/verify-redpanda-replay.sh [base-url]
# Failure: unavailable services, missing acknowledgement, restart failure, or missing replayed record.
# Evidence: prints the idempotency key, original offset, restart result, and replay match without payload contents.

set -Eeuo pipefail

BASE_URL="${1:-http://127.0.0.1:8080}"
TOPIC="${KAFKA_TOPIC:-nvt.telemetry.raw.v1}"
SEQUENCE="${REPLAY_SEQUENCE:-$(date +%s)}"
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
with open(sys.argv[1], "w", encoding="utf-8") as output:
    json.dump(
        {"envelope": chunk.envelope, "payload_base64": base64.b64encode(chunk.payload).decode("ascii")},
        output,
        separators=(",", ":"),
    )
print(f"replay_idempotency_key={chunk.envelope['idempotency_key']}")
PY

RESPONSE="$(curl --fail-with-body --silent --show-error \
    --header 'Content-Type: application/json' \
    --data-binary "@$TEMP_DIR/request.json" \
    "$BASE_URL/v1/telemetry/chunks")"

read -r QUEUE_TOPIC PARTITION OFFSET EXPECTED_KEY < <(
    uv run python - "$RESPONSE" <<'PY'
import json
import sys

response = json.loads(sys.argv[1])
if response.get("status") != "accepted" or not response.get("queue_offset"):
    raise SystemExit(f"ingestion did not return an accepted record: {response}")
topic, partition, offset = response["queue_offset"].rsplit(":", 2)
print(topic, partition, offset, response["idempotency_key"])
PY
)

printf 'accepted topic=%s partition=%s offset=%s\n' "$QUEUE_TOPIC" "$PARTITION" "$OFFSET"
./scripts/local-stack.sh restart redpanda
printf 'redpanda_restart result=passed\n'

./scripts/local-stack.sh exec redpanda rpk topic consume "$TOPIC" \
    --brokers redpanda:9092 --partitions "$PARTITION" --offset "$OFFSET" \
    --num 1 --format json --meta-only > "$TEMP_DIR/replay.json"

uv run python - "$TEMP_DIR/replay.json" "$EXPECTED_KEY" "$QUEUE_TOPIC" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as input_file:
    record = json.load(input_file)
expected_key = sys.argv[2]
expected_topic = sys.argv[3]
if record.get("topic") != expected_topic:
    raise SystemExit("replayed record topic did not match")
if record.get("key") != expected_key:
    raise SystemExit("replayed record key did not match")
print(f"replay topic={expected_topic} partition={record['partition']} offset={record['offset']} result=passed")
PY
