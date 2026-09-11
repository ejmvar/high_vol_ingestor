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

For failure recovery onboarding, read `docs/contracts/dlq.md`. It defines the
proposed distinction between transient retry, permanent rejection, semantic
quarantine, and downstream processing failure. The DLQ contract is design-only
until its provider-neutral port and verification tests are implemented.

## DLQ Onboarding

### The Problem It Solves

A telemetry record can fail for two fundamentally different reasons:

- The system is temporarily unable to process it. The record is still valid and
  should be retried.
- The record cannot safely continue. It must be preserved for inspection and a
  deliberate recovery decision.

The first case belongs to bounded retry. The second belongs to quarantine or a
DLQ. Treating both cases as the same error either loses valid telemetry during a
temporary outage or creates endless retries for a permanently invalid record.

### Decision Flow

Use this sequence when investigating an error:

1. Ask whether the input is valid according to the envelope and payload rules.
2. If it is valid, ask whether the failed dependency is expected to recover.
3. If recovery is expected, identify the component that owns the retry budget.
4. If the input is invalid or the retry budget is exhausted, preserve the raw
   record and create one logical quarantine entry.
5. Replay only after the cause is understood and the normal validation path is
   available again.

| Observation | Correct interpretation | First owner |
| --- | --- | --- |
| HTTP `503` with `backpressure` | Service capacity is temporarily full; the body was not read or published | Producer retries the same request |
| HTTP `503` with publisher failure | Broker or publisher operation failed transiently | Producer retries within its budget |
| HTTP `400` with `invalid_checksum` | The submitted bytes do not match the envelope | Ingestion boundary rejects; do not retry unchanged |
| HTTP `400` with `conflicting_duplicate` | An identity was reused for different content | Validator quarantines or escalates |
| Consumer retry budget exhausted | An accepted broker record repeatedly fails downstream | Failing consumer writes to DLQ |

### What Must Never Change

During quarantine and replay, the original telemetry identity and content are
authoritative. Do not change the `idempotency_key`, producer sequence, event
timestamps, checksum, or payload bytes to make a replay pass validation. If the
record needs correction, create an explicit corrected record with a new identity
and retain the original as lineage.

### Example Walkthrough

Suppose a consumer reads a record from the raw topic and cannot write its
curated representation:

1. The consumer retries the write with bounded backoff.
2. Each attempt keeps the original broker offset and `idempotency_key`.
3. After the retry budget is exhausted, the consumer writes the original
   envelope, exact payload, failure stage, stable reason code, attempt count,
   and source lineage to the DLQ.
4. The consumer acknowledges or advances the original record only after DLQ
   insertion succeeds, so a DLQ write failure cannot silently lose the record.
5. An operator or replay worker investigates the reason and replays the raw
   record through the normal path.
6. A successful destination acknowledgement, including an exact duplicate
   acknowledgement, resolves the DLQ entry. It does not create a second
   telemetry event.

### Onboarding Checklist

- [ ] I know whether my component is a producer, ingestion boundary, consumer,
  DLQ writer, or operator.
- [ ] I can distinguish transient `503` retry from permanent `400` rejection.
- [ ] I know which component owns my retry budget and when it ends.
- [ ] I preserve the original envelope and payload rather than using logs as a
  recovery source.
- [ ] I keep the original `idempotency_key` during DLQ insertion and replay.
- [ ] I can prove whether the destination accepted, duplicated, quarantined, or
  discarded the record.
- [ ] I do not claim DLQ durability until the implementation and evidence gates
  exist.

There is currently no DLQ persistence or replay command in the repository. The
contract is onboarding guidance and an implementation boundary, not an
operational procedure that can be executed yet.

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
