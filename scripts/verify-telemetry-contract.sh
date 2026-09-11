#!/usr/bin/env bash
# Intention: verify the telemetry schema and representative JSON fixtures.
# Expected result: exit 0 when all JSON documents parse and fixture expectations hold.
# Safety: read-only; does not start services, change files, or read secrets.
# Usage: ./scripts/verify-telemetry-contract.sh
# Failure: inspect the reported file or contract expectation, then rerun.
# Evidence: prints file names and validation outcomes only.

set -Eeuo pipefail

schema='schemas/telemetry/v1/envelope.schema.json'
valid='schemas/telemetry/v1/fixtures/valid-vibration.json'
invalid='schemas/telemetry/v1/fixtures/invalid-missing-checksum.json'

uv run python - "$schema" "$valid" "$invalid" <<'PY'
import json
import sys
from pathlib import Path

schema_path, valid_path, invalid_path = map(Path, sys.argv[1:])

for path in (schema_path, valid_path, invalid_path):
    with path.open(encoding="utf-8") as handle:
        json.load(handle)
    print(f"PARSED {path}")

schema = json.loads(schema_path.read_text(encoding="utf-8"))
required = set(schema["required"])
valid = json.loads(valid_path.read_text(encoding="utf-8"))
invalid = json.loads(invalid_path.read_text(encoding="utf-8"))

missing_valid = required - valid.keys()
if missing_valid:
    raise SystemExit(f"valid fixture missing required fields: {sorted(missing_valid)}")
print("VALID fixture has all schema-required fields")

missing_invalid = required - invalid.keys()
if "checksum" not in missing_invalid:
    raise SystemExit("invalid fixture must demonstrate a missing checksum")
print("INVALID fixture demonstrates missing checksum")
PY

printf 'Telemetry contract verification passed.\n'
