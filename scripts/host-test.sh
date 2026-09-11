#!/usr/bin/env bash
# Intention: run the canonical host-side Python test suite.
# Expected result: pytest exits 0 with all available tests passing.
# Safety: executes tests only; does not start services or access secrets.
# Usage: ./scripts/host-test.sh
# Failure: distinguish test failure from unavailable optional capabilities.
# Evidence: pytest output contains test results and no credentials.

set -Eeuo pipefail

uv run pytest
