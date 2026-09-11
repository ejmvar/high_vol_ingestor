# High-Volume Ingestor Onboarding

This repository provides one script-backed workflow through `mise`, Make, and
Just. The task runners are wrappers only; the scripts are the canonical
implementation and safety boundary.

## Quick Path

1. Install and activate `mise` and `uv`, plus Docker Compose or Podman Compose.
2. Run `mise run prerequisites`.
3. Run `mise run test`.
4. Run `mise run contract`.
5. Run `mise run stack-config`.
6. Start services with `mise run stack-up` only when local service execution is
   needed.

The same workflows are available with `make <task>` or `just <task>`.

## Task Surface

| Task | Canonical script | Side effect |
| --- | --- | --- |
| `prerequisites` | `scripts/check-prerequisites.sh` | Read-only tool check |
| `test` | `scripts/host-test.sh` | Runs host tests |
| `contract` | `scripts/verify-telemetry-contract.sh` | Read-only fixture check |
| `analytics-compatibility` | `scripts/verify-analytics-compatibility.sh` | In-memory adapter queries |
| `stack-config` | `scripts/local-stack.sh config` | Read-only Compose validation |
| `stack-up` | `scripts/local-stack.sh up` | Starts local containers |
| `stack-down` | `scripts/local-stack.sh down` | Stops containers, preserves volumes |
| `stack-ps` | `scripts/local-stack.sh ps` | Reads service status |
| `stack-logs` | `scripts/local-stack.sh logs` | Reads service logs |
| `check` | `test`, `contract`, `stack-config` | Combined read-only checks |

Run `mise run help`, `make help`, or `just help` for the same command list.

## Local Stack

The local Compose definition is at `deploy/local/compose.yaml`. It includes
the ingestor HTTP service, Redpanda, RustFS, ClickHouse, and PostgreSQL with
named persistent volumes.
See `docs/operations/local-stack.md` for ports, runtime selection, safety, and
failure interpretation.

The ingestor endpoint is available at `http://localhost:8080` after
`stack-up`; see `docs/operations/ingestor-service.md` for the request contract.
Its health endpoint proves process readiness only, not broker durability.

## Architecture Boundary

Domain and application behavior remains independent of task runners, container
engines, databases, queues, and HTTP. Scripts invoke adapters and operational
tools; task runners do not contain business logic.

## Common Results

- Missing Docker/Podman is a tooling-capability result.
- `stack-config` passing proves only Compose parsing and interpolation.
- `analytics-compatibility` exit `2` means an optional engine is unavailable;
  exit `1` means an available engine failed parity.
- Local service health does not prove durability, cloud equivalence, or
  production readiness.
