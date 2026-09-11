# Dead-Letter Queue Contract

Status: proposed design for the local prototype; not implemented or production-approved.

This document defines what happens when a telemetry record cannot continue through
the ingestion pipeline. A dead-letter queue (DLQ) is a quarantine and recovery
boundary, not a second success path: the original record remains available for
inspection and a later, deliberate replay.

## Quick Path

When onboarding a new producer or consumer, use this decision order:

1. Classify the failure as transient, permanent, or an operator quarantine.
2. Retry transient failures at the component that owns the failed operation.
3. Send permanent or quarantined records to the DLQ without changing their raw
   envelope or payload bytes.
4. Use the original `idempotency_key` for replay; never create a new telemetry
   identity just because the record entered the DLQ.
5. Record a bounded reason code, failure stage, and correlation identifier, then
   verify the DLQ entry can be located without logging payload contents.

## What A DLQ Is

The authoritative telemetry record is the original envelope plus its exact binary
payload. The DLQ stores a copy of that record together with recovery metadata so
an operator or replay worker can understand why processing stopped. It does not
rewrite the event timestamps, producer sequence, checksum, or idempotency key.

The DLQ is different from:

- a retry buffer, which is temporary ownership of a transient failure;
- a broker retention policy, which controls how long accepted records remain;
- an application error log, which is evidence only and must not be the recovery
  source;
- a duplicate acknowledgement, which is a successful idempotent outcome and
  must not create a DLQ entry.

## Failure Classes

| Class | Examples | Owner | DLQ action |
| --- | --- | --- | --- |
| Transient | Backpressure, broker unavailable, connection timeout, temporary downstream outage | The component that made the failed request | Retry with bounded backoff; do not DLQ on the first failure |
| Permanent contract failure | Malformed JSON, missing field, unsupported schema, invalid checksum, payload length mismatch | Ingestion boundary | Reject or quarantine with a stable reason code; never retry unchanged automatically |
| Semantic quarantine | Conflicting idempotency key, producer sequence regression, policy violation discovered by a consumer | Validator or consumer that owns the rule | Preserve the original record in the DLQ; require an explicit replay decision |
| Processing failure | A consumer repeatedly fails after the record was accepted, or exhausts its retry budget | The failing consumer | Write one DLQ entry after the bounded retry policy is exhausted |
| Operator quarantine | Manual hold for investigation, suspected corruption, or policy review | Operator or owning service | Add an auditable quarantine reason; do not mutate the original record |

The current HTTP adapter implements only the transient response boundary for
backpressure and publisher failure. It does not yet write DLQ records. A `503`
means the producer still owns retrying the same request; it is not evidence that
the request was accepted into a DLQ.

## Raw Record Preservation

Every DLQ entry must preserve, byte for byte:

- the original envelope representation, or a lossless structured equivalent;
- the exact decoded payload bytes;
- `payload_byte_length` and the original SHA-256 checksum;
- `schema_name` and `schema_version`, including unsupported versions;
- `idempotency_key`, `producer_id`, `motor_id`, and `producer_sequence` when
  present;
- `event_start` and `event_end` when present.

The DLQ wrapper may add metadata, but must not silently normalize or regenerate
the original content. At minimum, wrapper metadata should include:

| Field | Meaning |
| --- | --- |
| `dlq_schema_name` and `dlq_schema_version` | Version of the quarantine wrapper |
| `failure_stage` | Boundary where processing stopped, such as `http_validation`, `publisher`, or `consumer` |
| `reason_code` | Stable bounded code, not a free-form stack trace |
| `first_failed_at` and `last_failed_at` | UTC timestamps for the failure history |
| `attempt_count` | Number of attempts owned by the retrying component |
| `correlation_id` | Safe lookup identifier shared by logs and evidence |
| `original_topic`, `original_partition`, `original_offset` | Source location when the record was already accepted by a broker |

Payload bytes and secrets must not appear in ordinary logs. A checksum, offset,
correlation ID, and reason code are sufficient for routine diagnosis.

## Idempotency And Replay

The original `idempotency_key` remains the identity across initial delivery,
retry, DLQ insertion, and replay. A DLQ writer must be idempotent too: retrying
the write after a timeout must not create multiple logical quarantine records.

The proposed DLQ identity is the deterministic pair:

```text
(failure_stage, idempotency_key)
```

If the same record fails at multiple independent stages, each stage may have its
own entry, but the wrapper must retain the original identity and source lineage.
A conflicting reuse of an idempotency key must never overwrite the earlier raw
record; it is a separate conflict requiring operator review.

Replay must:

- read the preserved raw record, not a reconstructed payload from logs;
- retain the original `idempotency_key` and producer sequence;
- create a new replay-attempt identifier only for operational tracing;
- pass through the normal validation and idempotency rules;
- mark the DLQ entry as replayed only after the destination acknowledges it;
- remain safe if the replay command itself is repeated.

An exact duplicate acknowledged by the destination is a successful replay
outcome. It must not be counted as a newly created telemetry event.

## Retry Ownership

Ownership must be singular for each failure:

- The producer owns retrying `503/backpressure` and transient publisher failures.
- The ingestion boundary owns structural validation and decides whether a
  permanent contract error is rejected or quarantined.
- A downstream consumer owns retries after it has accepted a broker record.
- The DLQ writer owns durable quarantine insertion and must expose insertion
  failure separately from the original processing failure.
- An operator owns policy exceptions, manual release, and final discard approval.

No component may both retry indefinitely and emit an unbounded stream of DLQ
copies. Retry budgets, backoff, and the transition to DLQ must be explicit in
the component contract.

## State Model

The proposed lifecycle is:

```text
received -> processing -> retrying -> quarantined -> replaying -> resolved
                                      \-> discarded
```

`resolved` means the replay destination acknowledged the record or an exact
duplicate was safely acknowledged. `discarded` requires an operator decision and
an auditable reason. Neither state permits deletion of the original raw evidence
unless the applicable retention and governance policy explicitly allows it.

## Acceptance Checklist

- [ ] Each failure code maps to exactly one retry owner.
- [ ] Transient `503` responses are not incorrectly described as DLQ acceptance.
- [ ] A permanent failure preserves the original envelope and payload bytes.
- [ ] DLQ insertion is idempotent and does not overwrite conflicting records.
- [ ] Replay reuses the original telemetry identity and passes normal validation.
- [ ] Duplicate replay is reported as resolved/idempotent, not as a new event.
- [ ] Logs contain only bounded metadata and safe correlation values.
- [ ] Retry exhaustion, DLQ insertion, replay, resolution, and discard produce
  secret-safe evidence.
- [ ] Retention, access control, and deletion policy are specified before any
  production durability claim.

## Current Boundary And Next Implementation

The repository currently proves validation, idempotency, broker acceptance,
restart/replay, retention behavior on a temporary topic, and HTTP backpressure.
It does not yet prove DLQ persistence or replay.

The next implementation increment should add a provider-neutral quarantine port
and an in-memory test double before selecting a Kafka, object-store, or database
adapter. The increment must first add tests for deterministic DLQ identity, raw
payload preservation, retry ownership, and idempotent replay.
