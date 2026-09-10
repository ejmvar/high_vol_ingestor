# Portable High-Volume Motor Telemetry Demo Plan

## Executive recommendation

Build the demo around Kafka-protocol producers and consumers, using **Redpanda in Docker Compose** as the local durable queue. Store append-only raw chunks in an S3-compatible object-store port (evaluate **RustFS** locally), write curated telemetry, aggregates, and features to a single-node Dockerized **ClickHouse**, and use the existing **PostgreSQL/TimescaleDB** for catalog/metadata and optional low-rate operational data.

This separates durable capture from analytics and preserves a cloud migration path. A future managed Kafka-compatible broker or S3-compatible store is possible through environment adapters; it is **not** assumed to be a drop-in replacement because security, IAM, networking, retention, and managed connectors differ by provider.

### Non-goals

- Do not make the demo a production availability, compliance, or legal-immutability claim.
- Do not make TimescaleDB the default store for high-rate raw telemetry.
- Do not store authoritative raw audio or ultrasonic payloads in ClickHouse.
- Do not select a cloud provider before validating the local data contract and workload.

## Signal and chunk contract

All simulated data creators upload to the ingestion endpoint. The endpoint validates and publishes a versioned envelope; it must not rely on producer-local state for ordering or deduplication.

| Signal | Source cadence | Payload unit |
|---|---:|---|
| `Vin` for `MOTOR-c2ad` | 1 ms | electrical sample; batch into a 1-second window |
| `Iin` for `MOTOR-c2ad` | 1 ms | electrical sample; batch into a 1-second window |
| Active power for `MOTOR-c2ad` | 1 ms | electrical sample; batch into a 1-second window |
| Vibration amplitude for `MOTOR-c2ad` | 1 second | one 1-second frame |
| Audio sensing (10 Hz–20 kHz) for `MOTOR-c2ad` | 1 second | one 1-second chunk |
| High-frequency sensing (20–100 kHz) for `MOTOR-c2ad` | 1 second | one 1-second chunk |

Every window or chunk must include: `motor_id`, signal type, event start/end timestamps (UTC), sample rate, sample/channel count, monotonically increasing producer sequence, payload byte length, checksum, schema name/version, codec/format, and an idempotency key. Use 1-second audio/ultrasonic chunks and 1-second electrical windows. Object keys are append-only and derived from stable identity fields, for example: `raw/v1/<motor>/<signal>/<date>/<start>-<sequence>-<checksum>`.

## Portable local-to-cloud deployment profile

| Component | Local demo responsibility | Cloud portability boundary |
|---|---|---|
| Ingestion service | Validate envelope, assign/reject malformed records, publish to queue | Kafka-protocol client configuration and provider-specific authentication/network adapter |
| Redpanda (Docker Compose) | Durable local queue, topic retention, replay, consumer isolation | Replace with a Kafka-compatible managed service only after adapter and operational validation |
| RustFS (Docker Compose evaluation) | Candidate raw-object store with persistent data/log volumes and S3 API | S3 API port plus required compatibility smoke test before it becomes a migration baseline |
| ClickHouse (single-node Docker) | Curated telemetry, aggregates, feature tables, analytical queries; persistent `/var/lib/clickhouse` volume | Deployment, access, and capacity adapter; monitor laptop memory and disk |
| PostgreSQL/TimescaleDB | Dataset catalog, lineage, ingestion/audit metadata, and optional low-rate relational/operational data | Managed database adapter; do not duplicate high-rate raw telemetry by default |

## Durable ingestion and failure semantics

1. The endpoint acknowledges a producer only after the queue has accepted the record durably according to the selected local broker configuration.
2. Consumers are idempotent: the contract identity/key prevents duplicate raw objects and duplicate curated writes.
3. Raw persistence is the priority sink. Curated transforms and feature generation are replayable consumers, never the only copy of a received chunk.
4. Retry transient failures with bounded exponential backoff. Route poison records to a dead-letter queue (DLQ) with failure reason and original envelope.
5. Apply backpressure at the endpoint and producers when queue, object-store, or disk thresholds are exceeded; expose lag, rejected records, DLQ count, and raw-sink success as operational metrics.
6. Recover by replaying queue offsets into the raw sink or downstream processors after verifying idempotency and available retention.

## Storage and data tiers

| Tier | System of record | Content and rules |
|---|---|---|
| Raw | S3-compatible object storage | Original chunks/windows, append-only keys, checksums, source schema/version, explicit retention/lifecycle policy. Local storage is not described as legally immutable until object-lock/versioning and policy behavior are validated. |
| Curated | ClickHouse | Normalized telemetry references, quality flags, time buckets, aggregates, and query-ready representations. Keep a pointer to the raw object identity/checksum. |
| Features | ClickHouse plus catalog metadata | Derived frames, preprocessing version, feature definition/version, model/pipeline provenance, and input raw/curated lineage. |
| Catalog | PostgreSQL/TimescaleDB | Dataset registry, schema registry, object/partition inventory, producer and processing runs, retention state, and discoverability for new ML pipelines. |

Preprocessing may compress, simplify, and create presentation-ready frames, but it must retain lineage to raw data so a later analysis pipeline can discover and use historic data. Lifecycle deletion must be explicit and recorded in the catalog.

## Initial sizing (assumptions, not a capacity commitment)

Assume four simultaneous motors, mono 16-bit PCM, audio at 20 kHz, ultrasonic/high-frequency sensing at 100 kHz, and one year of production raw retention:

- Per motor: audio `20,000 samples/s × 2 bytes = 40 KB/s`; high-frequency `100,000 × 2 = 200 KB/s`; total **240 KB/s** before envelope and compression.
- Four motors: **960 KB/s**, or roughly **30 TB/year decimal** before replication, metadata, indexes, and operational headroom.
- Electrical channels at 1 kHz are comparatively small under these assumptions.

Actual volume depends on channel count, bit depth, codec, and whether vibration is a scalar amplitude or a waveform. Validate the estimate with a one-hour representative capture, including object, queue, and ClickHouse overhead. Demo retention must be configurable and normally much shorter than the one-year production target; laptop disk and memory must be monitored.

## Delivery phases

1. **Prototype** — Implement the six generators, versioned endpoint contract, Redpanda topics, and raw object persistence for one motor.
2. **Reliability** — Add durable-ack evidence, idempotency, DLQ, retry/backpressure, queue retention, and controlled replay tests.
3. **Preprocessing** — Create replayable consumers for compression, quality checks, curated records, and feature frames with lineage.
4. **Serving and catalog** — Add ClickHouse analytical tables and PostgreSQL/TimescaleDB catalog/discovery records for historical ML use.
5. **Scale and recovery validation** — Run four-motor and one-hour capture tests; validate restart, backlog, replay, retention, disk thresholds, and cloud-adapter smoke tests.

## Queue decision matrix

| Option | Fit for this stream | Decision |
|---|---|---|
| Redpanda | Kafka API, replayable durable log, Docker Compose-friendly local operation | **Select now** for the demo. |
| Apache Kafka | Strong replayable-stream fit and widest ecosystem | Viable future/local alternative; more operational weight for this demo. |
| RabbitMQ | Strong work queues and routing; less natural for long retention and analytics replay | Not the default. |
| Redis Streams | Simple local stream option; persistence/operations need deliberate validation at this volume | Not the default. |
| NATS JetStream | Efficient messaging with persistence; ecosystem and Kafka-protocol portability differ | Not the default. |

Redpanda is selected because the workload needs durable, replayable high-volume streams and a Kafka-protocol path to managed services. Broker choice alone does not provide end-to-end durability: host disks, acknowledgements, replication, retention, and recovery procedures must be configured and tested.

## Acceptance checks

- [ ] All six signals are generated, accepted, and discoverable by motor, signal, timestamp, and schema version.
- [ ] Each one-second chunk/window has sequence, checksum, format, and idempotency identity.
- [ ] Acknowledgements occur only after configured durable queue acceptance; duplicate delivery and consumer replay do not create duplicate raw or curated records.
- [ ] RustFS/S3 compatibility smoke test covers multipart upload, presigned read, checksum/ETag behavior, and lifecycle rules before migration-baseline approval.
- [ ] Raw objects have append-only keys, cataloged retention/lifecycle behavior, and raw-to-curated-to-feature lineage.
- [ ] ClickHouse contains curated/feature data only; PostgreSQL/TimescaleDB contains catalog/metadata and optional low-rate operational data.
- [ ] Four-motor one-hour capture measures actual throughput, storage, queue lag, and laptop disk/memory headroom.
- [ ] Restart, backpressure, DLQ, and replay recovery are demonstrated with recorded evidence.

## Unresolved decisions and risks

| Item | Risk or decision required |
|---|---|
| Actual sample format and channels | Sizing can change materially with stereo/multichannel input, bit depth, codec, and waveform-vs-scalar vibration. |
| Laptop resources | Single-node queue, object store, and ClickHouse compete for disk, memory, and I/O; establish thresholds before reliability testing. |
| Cloud target | Select provider/managed services later; define IAM, private networking, encryption, retention, managed connectors, and cost model in the environment adapter. |
| Retention and compliance | Confirm production retention, deletion, versioning/object lock, backup, and legal/compliance requirements before any immutability claim. |
| Queue durability | Confirm local broker acknowledgement, replication, disk, and retention settings through failure testing rather than defaults. |
