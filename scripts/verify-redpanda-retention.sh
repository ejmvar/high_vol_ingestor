#!/usr/bin/env bash
# Intention: verify bounded time-based retention on a temporary Redpanda topic.
# Expected result: a produced record is initially present and later removed after retention expiry.
# Safety: creates and deletes only a uniquely named temporary topic; application data and named volumes remain untouched.
# Usage: ./scripts/verify-redpanda-retention.sh
# Failure: unavailable broker, invalid topic configuration, or missing initial record.
# Capability result: exit 2 when retention is configured but deletion is not observed.
# Evidence: prints topic configuration and before/after log offsets without payload contents.

set -Eeuo pipefail

TOPIC="nvt.retention.smoke.$(date +%s)"
BROKERS="redpanda:9092"
RETENTION_MS=5000
SEGMENT_MS=1000
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"; ./scripts/local-stack.sh exec redpanda rpk topic delete "$TOPIC" --brokers "$BROKERS" >/dev/null 2>&1 || true' EXIT

for attempt in {1..30}; do
    if ./scripts/local-stack.sh exec redpanda rpk cluster health --api-urls redpanda:9644 >/dev/null 2>&1; then
        break
    fi
    if [[ "$attempt" == 30 ]]; then
        printf 'ERROR Redpanda did not become ready within 60 seconds\n' >&2
        exit 1
    fi
    sleep 2
done

./scripts/local-stack.sh exec redpanda rpk topic create "$TOPIC" \
    --brokers "$BROKERS" --partitions 1 --replicas 1 \
    --topic-config "cleanup.policy=delete" \
    --topic-config "retention.ms=$RETENTION_MS" \
    --topic-config "retention.local.target.ms=$RETENTION_MS" \
    --topic-config "segment.ms=$SEGMENT_MS" \
    --topic-config "segment.bytes=16384"

./scripts/local-stack.sh exec redpanda rpk topic alter-config "$TOPIC" --brokers "$BROKERS" \
    --set "retention.ms=$RETENTION_MS" \
    --set "retention.local.target.ms=$RETENTION_MS" \
    --set "segment.ms=$SEGMENT_MS" \
    --set "segment.bytes=16384"

printf 'retention-probe-%s\n' "$TOPIC" | \
    ./scripts/local-stack.sh exec redpanda rpk topic produce "$TOPIC" --brokers "$BROKERS"

sleep 2
uv run python - <<'PY' | \
    ./scripts/local-stack.sh exec redpanda rpk topic produce "$TOPIC" --brokers "$BROKERS"
for index in range(20):
    print(f"retention-probe-{index}-" + "x" * 20000)
PY

sleep 2
printf 'retention-probe-rollover-%s\n' "$TOPIC" | \
    ./scripts/local-stack.sh exec redpanda rpk topic produce "$TOPIC" --brokers "$BROKERS"

./scripts/local-stack.sh exec redpanda rpk topic describe "$TOPIC" \
    --brokers "$BROKERS" --format json > "$TEMP_DIR/before.json"

uv run python - "$TEMP_DIR/before.json" "$TOPIC" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as input_file:
    document = json.load(input_file)
partition = document[0]["partitions"][0]
if partition["high_watermark"] < 1 or partition["log_start_offset"] != 0:
    raise SystemExit(f"retention probe record was not present: {partition}")
configs = {item["key"]: item["value"] for item in document[0]["configs"]}
if (
    configs.get("retention.ms") != "5000"
    or configs.get("retention.local.target.ms") != "5000"
    or configs.get("segment.ms") != "1000"
    or configs.get("segment.bytes") != "16384"
):
    raise SystemExit(f"retention configuration was not applied: {configs}")
print(f"retention_config topic={sys.argv[2]} retention_ms=5000 retention_local_target_ms=5000 segment_ms=1000 segment_bytes=16384")
print(f"retention_before log_start_offset={partition['log_start_offset']} high_watermark={partition['high_watermark']}")
PY

# Allow segment closure and the broker's background cleanup cycle to run.
sleep 75

./scripts/local-stack.sh exec redpanda rpk topic describe "$TOPIC" \
    --brokers "$BROKERS" --format json > "$TEMP_DIR/after.json"

uv run python - "$TEMP_DIR/after.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as input_file:
    document = json.load(input_file)
partition = document[0]["partitions"][0]
if partition["log_start_offset"] < 1:
    print(f"retention result=unavailable reason=deletion_not_observed partition={partition}")
    raise SystemExit(2)
print(f"retention_after log_start_offset={partition['log_start_offset']} high_watermark={partition['high_watermark']} result=passed")
PY
