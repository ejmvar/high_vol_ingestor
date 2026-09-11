#!/usr/bin/env bash
# Intention: install the project's Kafka optional dependencies with uv.
# Expected result: the locked Kafka and Zstandard packages are installed and the codec imports.
# Safety: updates only the project virtual environment and uv lock state; it does not contact local services.
# Usage: ./scripts/sync-kafka-dependencies.sh
# Failure: uv resolution/install failure or unavailable Zstandard import.
# Evidence: prints package versions and a secret-free pass/fail result.

set -Eeuo pipefail

uv sync --extra kafka

uv run --extra kafka python - <<'PY'
import importlib.metadata
import zstandard

print(f"kafka-python={importlib.metadata.version('kafka-python')}")
print(f"zstandard={zstandard.__version__}")
print("kafka_codec result=passed")
PY
