# Development Phase Log

This document records the development phases completed for the high-volume
telemetry ingestor. Each phase states its intention, observable behavior,
implementation boundary, situations evaluated, evidence, and deliberately
deferred work. The purpose is to let a reviewer understand why the repository
is shaped this way without reconstructing the entire session history.

## Reading This Log

The phases are ordered by dependency. A later phase may use an earlier phase,
but each commit should remain independently understandable and removable.

The repository currently proves contract and in-memory behavior. It does not
yet prove Redpanda durability, object-store persistence, cloud portability, or
production readiness.

## Phase 1: Prerequisite Workflow

### Intention

Create a safe, repeatable first check for the tools needed by local
development. The check must be read-only and must not make developers guess
which commands or versions are required.

### Behavior

`./scripts/check-prerequisites.sh` reports the presence and versions of
`docker`, `mise`, `uv`, and the Docker Compose plugin. Terraform is reported
when present but is optional at this stage. The command exits successfully only
when all required tools are available.

The script does not start containers, install tools, inspect secrets, or claim
that the Docker daemon is healthy. Those are separate operational concerns.

### Implementation

- `scripts/check-prerequisites.sh` contains strict shell settings and explicit
  required/optional tool handling.
- `docs/operations/check-prerequisites.md` defines intention, usage, expected
  result, safety, failure interpretation, and evidence.
- Commit `b0987e3` is the integrated form of the original handoff `733a0db`.

### Situations Evaluated

- Required command present and version command succeeds.
- Required command absent.
- Docker present but Compose plugin absent.
- Optional Terraform absent.
- Version command failure, which is treated as an installation problem rather
  than silently ignored.

### Deliberately Deferred

- Docker daemon health.
- Container startup and service readiness.
- Cloud authentication and Terraform execution.
- Resource-capacity or production-readiness claims.

## Phase 2: Industrial Vibration Research

### Intention

Establish an evidence boundary before selecting sampling defaults or building
producers. Industrial vibration data is useful only when the signal remains
connected to its sensor installation, operating state, processing method, and
maintenance decision.

### Behavior

The research document distinguishes three things that must not be conflated:

- Acquisition rate: how frequently the physical signal is sampled.
- Publication rate: how frequently features or waveform chunks are sent.
- Retention period: how long each data class remains available for replay.

It records pilot starting points for scalar features, scheduled waveforms, and
event-triggered waveforms, but labels them as proposals rather than universal
industry requirements.

### Implementation

`docs/research/industrial-vibration-monitoring.md` documents:

- sensor families and mounting implications;
- sample-rate and window-selection reasoning;
- time-domain and frequency-domain evidence;
- candidate failure hypotheses and required context;
- edge processing and durable-ingestion boundaries;
- dashboard requirements, including stale-data visibility;
- layered retention proposals;
- pilot acceptance questions and open research gaps;
- a source register with access date and evidence scope.

### Situations Evaluated

- Slow equipment versus machinery requiring high-frequency bearing or gear
  evidence.
- Continuous scalar features versus replayable waveform evidence.
- Rigid, magnetic, and adhesive sensor mounting.
- Fixed-frequency comparison versus variable-speed/order-conditioned analysis.
- Healthy-looking stale data versus current, quality-flagged data.
- Local S3-compatible storage versus a legally immutable storage claim.

### Deliberately Deferred

- A single universal sample rate.
- A universal retention mandate.
- Automatic failure classification without real maintenance history.
- Exact ISO limits without reviewing the applicable licensed standard parts.

## Phase 3: Versioned Telemetry Envelope

### Intention

Define the provider-neutral message identity before implementing generators,
brokers, or cloud adapters. The envelope is the contract between a producer and
the ingestion boundary.

### Behavior

Each vibration, electrical, audio, or ultrasonic window identifies its asset,
signal, time interval, sampling shape, producer order, payload bytes, checksum,
schema version, encoding, and idempotency identity.

The payload bytes are treated as separate binary content. Metadata records the
exact byte length and SHA-256 digest so raw persistence and downstream replay
can verify what was received.

### Implementation

- `schemas/telemetry/v1/envelope.schema.json` defines the structural v1 shape.
- `schemas/telemetry/v1/fixtures/valid-vibration.json` is a minimum valid
  envelope.
- `schemas/telemetry/v1/fixtures/invalid-missing-checksum.json` is a structural
  failure fixture.
- `docs/contracts/telemetry-envelope.md` defines identity, ordering,
  compatibility, and failure semantics.
- `scripts/verify-telemetry-contract.sh` performs the repeatable fixture check.
- Commit `97517e9` contains the contract work unit.

### Situations Evaluated

- Valid vibration envelope.
- Missing required checksum.
- Unsupported schema name or version.
- Unsupported signal, codec, or format.
- Invalid numeric metadata.
- Timestamp and payload rules that JSON Schema cannot fully express.

### Deliberately Deferred

- Duplicate detection based on prior accepted records.
- Out-of-order detection based on producer history.
- Verifying a digest against actual payload bytes.
- Queue topic names and broker-specific headers.

## Phase 4: Structural and Stateful Validation

### Intention

Turn the envelope rules into executable behavior before introducing transport.
The validator is deliberately pure so it can be reused by an HTTP endpoint,
Kafka adapter, batch importer, or replay consumer.

### Behavior

`validate_envelope` rejects malformed records, missing or unknown fields,
unsupported versions, invalid timestamps, invalid intervals, invalid numeric
values, invalid checksum metadata, payload-length mismatches, and checksum
mismatches.

`StatefulTelemetryValidator` adds two state-machine rules:

- The same idempotency key with the same payload metadata is a safe duplicate.
- A new record must increase the producer sequence for the producer/motor
  pair.

A reused idempotency key with different checksum or length is a conflicting
  duplicate and is rejected.

### Implementation

- `telemetry_contract/validator.py` contains stable error reason codes.
- `tests/test_telemetry_validator.py` contains eight focused tests.
- `pyproject.toml` configures pytest to import the repository package.
- `.gitignore` prevents generated Python test caches from entering commits.
- Commits `1936e6e`, `65fd7eb`, and `4d13a1e` contain this work and its cleanup.

### Situations Evaluated

- Valid mapping accepted.
- Non-object record rejected.
- Missing checksum rejected.
- Equal or reversed event interval rejected.
- Payload length and digest mismatch rejected.
- Exact duplicate acknowledged without creating a new logical record.
- Conflicting duplicate rejected.
- Sequence regression or reuse rejected.

### Important Design Finding

JSON Schema cannot evaluate prior records or binary payloads. Stateful ordering,
idempotency, and checksum-vs-bytes checks therefore belong in runtime code and
must not be hidden behind a schema-only acceptance claim.

## Phase 5: Deterministic Vibration Producer

### Intention

Create a reproducible source of realistic-enough vibration bytes for contract,
pipeline, and later storage tests. Determinism makes failures reproducible and
allows a consumer to compare replayed results.

### Behavior

`generate_vibration_chunk` emits mono signed 16-bit little-endian PCM. The
caller controls sample rate, duration, base frequency, amplitude, noise seed,
motor identity, producer identity, and sequence.

The generator derives sample count, event end, payload length, SHA-256, event
identity, and quality metadata from the emitted content and configuration. It
marks `quality.clipped` when a generated sample exceeds the representable PCM
range before clamping.

### Implementation

- `telemetry_contract/generator.py` implements the pure generator.
- `telemetry_contract/__init__.py` exports the public API.
- `tests/test_vibration_generator.py` contains five tests.
- Commit `c8f6d97` contains the producer work unit.

### Situations Evaluated

- Same seed and start time produce identical payload and envelope.
- Different seed changes payload and checksum.
- Duration and sample rate determine exact sample count and end time.
- Generated bytes match declared length and checksum.
- Excessive amplitude/noise is clamped and reported as clipping.
- Naive timestamps, non-positive rates, invalid durations, and negative
  sequences are rejected.

### Deliberately Deferred

- NumPy or DSP acceleration.
- Bearing impulse, imbalance, misalignment, and other fault models.
- Hardware sensor calibration and analog front-end behavior.
- Continuous unbounded generation.

## Phase 6: Consecutive Chunk Stream

### Intention

Provide a bounded producer interface that can model a short capture without
making the generator responsible for clocks, queues, or process lifetime.

### Behavior

`generate_vibration_chunks` yields a requested number of chunks. Each chunk has
an incremented producer sequence and an event interval that begins exactly when
the preceding interval ends. A caller can choose a non-zero initial sequence
and an aware UTC start time.

### Implementation

- `telemetry_contract/stream.py` derives each configuration with a new sequence
  and contiguous start time.
- `tests/test_vibration_stream.py` contains four tests.
- Commit `3ff170d` contains the stream work unit.

### Situations Evaluated

- Three contiguous one-second chunks.
- Non-zero initial sequence.
- Repeated generation with the same configuration.
- Negative count rejection.
- Missing timezone rejection.

### Deliberately Deferred

- Real-time sleeping or wall-clock scheduling.
- Backpressure and cancellation.
- Unbounded streams.
- Publication retries; those belong at the ingestion boundary.

## Phase 7: Transport-Neutral Ingestion Boundary

### Intention

Define the acceptance point where a validated record becomes eligible for
durable publication. The boundary must not depend on Redpanda implementation
details, while preserving the guarantee that failed publication can be retried.

### Behavior

`IngestionEndpoint` first inspects the envelope and payload. For a new valid
record it calls the `DurablePublisher` port, waits for the publisher's
acceptance offset, and only then commits validator state. An exact duplicate is
acknowledged without republishing. A conflicting duplicate, invalid record, or
ordering regression never reaches the publisher.

If publication raises an error, the validator has not recorded the record, so a
retry can submit the same sequence without being incorrectly rejected as out of
order.

### Implementation

- `telemetry_contract/ingestion.py` defines `DurablePublisher`,
  `IngestionReceipt`, and `IngestionEndpoint`.
- `StatefulTelemetryValidator.inspect` performs validation without committing;
  `commit` records state after publisher acceptance.
- `tests/test_ingestion_endpoint.py` uses an explicit fake publisher and covers
  publication ordering, duplicate suppression, retry after publisher failure,
  and invalid-record rejection.
- Commit `3c1922d` contains this work unit.

### Situations Evaluated

- Valid record published and receives an acceptance offset.
- Exact duplicate returns `duplicate` and does not republish.
- Publisher failure leaves sequence state available for retry.
- Invalid payload metadata is rejected before publisher invocation.
- Conflicting duplicate and out-of-order behavior remains delegated to the
  validator.

### Deliberately Deferred

- HTTP request parsing and response serialization.
- Redpanda/Kafka producer configuration.
- Broker acknowledgement, replication, disk persistence, retention, and
  restart semantics.
- Raw object-store writes and ClickHouse projections.

## Verification Evidence

The complete current Python test suite passes with `21 passed` using:

```bash
uv run pytest
```

The contract fixture verification passes using:

```bash
./scripts/verify-telemetry-contract.sh
```

These checks prove local pure-Python behavior only. They do not prove service
availability, throughput, durability, cloud compatibility, or production
readiness.

## Next Development Gate

The next phase is the local durable queue adapter. It must be introduced as a
separate work unit with its own documented script and evidence. Before calling
it durable, the verification must demonstrate configured acknowledgement,
persistence across restart, retention/replay behavior, duplicate handling,
backpressure, and a failure-safe dead-letter path.

The existing working tree contains unrelated untracked material and an
unstaged TODO edit in `telemetry_contract/generator.py`; those items are not
part of the completed phases and must remain outside future commits until their
ownership is clear.
