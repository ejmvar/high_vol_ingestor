# Telemetry Envelope Contract

Status: version 1.0 draft for the local prototype

Canonical schema: `schemas/telemetry/v1/envelope.schema.json`

## Purpose

The envelope identifies one bounded telemetry window or chunk before it enters
the durable queue. It is independent of Kafka, Redpanda, S3, ClickHouse, and
PostgreSQL so those systems remain replaceable adapters.

The payload bytes are transported separately from this JSON metadata. The
`payload_byte_length` and SHA-256 checksum cover the exact bytes submitted for
the chunk, before storage or downstream transformation.

## Identity and Ordering

- `idempotency_key` is the stable identity used to suppress duplicate delivery.
- `producer_sequence` is monotonically increasing per `producer_id` and
  `motor_id`; consumers reject or quarantine regressions according to their
  ordering policy.
- `event_start` and `event_end` describe the signal time in UTC and must not be
  replaced by queue-ingestion time.
- `event_end` must be later than `event_start`; this cross-field rule is not
  expressible in the current basic schema and must be checked by the endpoint.

## Compatibility

Consumers must accept the exact `schema_name` and `schema_version` they declare
support for. A new incompatible field or semantic change requires a new major
version. Additive optional fields may remain within the same major version only
after consumers are tested for unknown-field behavior.

## Failure Handling

- Malformed JSON or schema-invalid records are rejected before queue publish.
- Checksum failure is rejected before durable acknowledgement.
- Duplicate `idempotency_key` is acknowledged only when it matches the existing
  accepted record; a conflicting payload is quarantined.
- Out-of-order records are not silently discarded. The endpoint or consumer
  records the sequence decision and retains the original envelope in the DLQ
  when policy requires quarantine.
- Every rejection includes a bounded reason code and correlation identifier;
  secrets and payload bytes must not be written to ordinary logs.

The detailed proposed quarantine and replay contract is documented in
`docs/contracts/dlq.md`. It is not yet an implemented persistence guarantee.

## Fixtures

- `valid-vibration.json` is the minimum valid vibration envelope.
- `invalid-missing-checksum.json` demonstrates a schema-invalid record.

Duplicate, out-of-order, and checksum-failing cases are semantic fixtures for
the endpoint and consumer tests; they cannot be represented by JSON Schema
alone because they require prior records or payload bytes.
