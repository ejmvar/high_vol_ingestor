#!/usr/bin/env bash
# Intention: compare available analytics adapters against the canonical fixture.
# Expected result: exit 0 when all requested engines are available and match; exit 2 when optional engines are unavailable.
# Safety: read-only in-memory queries; does not start services, change files, or read secrets.
# Usage: ./scripts/verify-analytics-compatibility.sh
# Failure: exit 1 means an available adapter failed parity; exit 2 means capability is unavailable.
# Evidence: prints adapter names and PASS/UNAVAILABLE/FAIL outcomes only.

set -Eeuo pipefail

uv run python -m analytics_contract.verify
