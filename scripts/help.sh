#!/usr/bin/env bash
# Intention: show the canonical local development workflows.
# Expected result: print only commands backed by repository scripts.
# Safety: read-only; does not start services or access secrets.
# Usage: ./scripts/help.sh
# Failure: a missing listed script indicates an onboarding regression.
# Evidence: prints task names, intentions, and canonical commands only.

set -Eeuo pipefail

cat <<'HELP'
High-volume ingestor local workflows

  prerequisites             Check Docker/Podman, mise, uv, and Compose tools
  test                     Run the canonical host test suite
  contract                 Verify telemetry schema fixtures
  analytics-compatibility  Compare available DuckDB/chDB adapters
  stack-config             Validate the Docker/Podman Compose definition
  stack-up                 Start Redpanda, RustFS, ClickHouse, and PostgreSQL
  stack-down               Stop services and preserve named volumes
  stack-ps                 Show service status and health
  stack-logs               Show service logs
  check                    Run host tests and read-only contract checks

Canonical entry points:
  mise run <task>
  make <task>
  just <task>

Analytics compatibility exits 2 when optional engines are unavailable.
Stack reset is intentionally not exposed as a default task; use
CONFIRM_LOCAL_RESET=YES ./scripts/local-stack.sh reset explicitly.
HELP
