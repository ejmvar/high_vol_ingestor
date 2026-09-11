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

## Phase 11: Unified Onboarding Task Surface

### Intention

Make every current operational workflow discoverable through the repository's
task runners and one onboarding path. Task runners are intentionally wrappers;
the scripts remain the canonical operational boundary.

### Behavior

`mise`, Make, and Just expose the same task names for prerequisites, tests,
contract checks, analytics compatibility, local-stack configuration and
lifecycle, logs/status, and the combined read-only check. Their help output is
generated by the same `scripts/help.sh` file so task descriptions cannot drift.

### Implementation

- `mise.toml`, `Makefile`, and `Justfile` expose equivalent project-local tasks.
- `scripts/host-test.sh` is the canonical host-test entry point.
- `scripts/help.sh` is the shared onboarding help source.
- `docs/ONBOARDING.md` is the unified developer entry point.
- `docs/operations/host-test.md` documents the test script.

### Situations Evaluated

- A new developer starts from `mise`, Make, or Just.
- Help output must list only scripts that exist in this repository.
- A task must be runnable without embedding business logic in the task runner.
- Analytics dependencies may be unavailable without making unit tests fail.
- Stack validation must not start containers.
- Destructive volume reset must not be exposed as a default task.

### Deliberately Deferred

- Automatically installing Docker, Podman, or optional analytics engines.
- Claiming onboarding success without a clean-checkout run on each supported
  task runner.

## Phase 12: Local Ingestor Application Service

### Intention

Make the application boundary runnable locally by composing the HTTP transport
adapter, provider-neutral ingestion endpoint, and Kafka-compatible publisher in
one container. The service must be replaceable without changing the envelope,
validator, or ingestion port.

### Behavior

`POST /v1/telemetry/chunks` accepts an envelope and base64 payload, validates
them, publishes the exact bytes to the configured Kafka topic, and returns a
queue offset after the producer future resolves. Exact duplicates return
without republishing. `GET /health` reports process readiness only.

Invalid requests return `400`; publisher failures return `503`; unknown routes
return `404`. Request payloads are bounded and are not written to ordinary
access logs.

### Implementation

- `ingestor_http/server.py` provides the standard-library HTTP adapter.
- `ingestor_service/__main__.py` composes environment configuration and ports.
- `deploy/local/Dockerfile.ingestor` builds the local application image.
- `deploy/local/compose.yaml` includes the `ingestor` service on port `8080`.
- `docs/operations/ingestor-service.md` documents its transport contract.
- `tests/test_http_adapter.py` covers request/response and readiness behavior.
- Commit `b878b94` contains the runnable service slice.

### Situations Evaluated

- Accepted record waits for publisher acknowledgement.
- Exact duplicate avoids a second publish.
- Invalid base64 is rejected before publisher invocation.
- Unknown routes are rejected.
- Health readiness does not expose secrets or payload data.
- Container configuration uses service-name Kafka addressing rather than host
  addresses.
- Local service health is distinguished from broker durability.

### Deliberately Deferred

- TLS, authentication, rate limiting, and production network policy.
- Real broker smoke test, persistence, restart, retention, replay, and DLQ
  evidence.
- Graceful HTTP shutdown and bounded publisher close behavior under forced
  container termination.
- High-volume payload transport optimization beyond the initial base64 HTTP
  contract.

## Phase 13: Kafka Codec Reproducibility

### Intention

Make the Kafka publisher's selected Zstandard compression capability explicit
and reproducible in both the host development environment and the local
container image.

### Behavior

`mise run kafka-sync` resolves the `kafka` optional dependency extra through
`uv`, verifies that `kafka-python` and `zstandard` are importable, and prints
their versions without exposing secrets. The local image installs the same
codec as a pinned runtime dependency.

### Implementation

- `pyproject.toml` declares `zstandard` in the `kafka` optional extra.
- `uv.lock` records the resolved optional dependency.
- `scripts/sync-kafka-dependencies.sh` is the documented installation and
  verification entry point.
- `mise.toml` exposes the script as `kafka-sync`.
- `deploy/local/Dockerfile.ingestor` pins the container installation.
- `docs/operations/ingestor-service.md` records the failure and decision.

### Situations Evaluated

- A producer configured for Zstandard without its codec fails during startup.
- Host and container dependency paths are independently reproducible.
- Disabling compression would remove the dependency but worsen high-volume
  transport and storage efficiency.

### Deliberately Deferred

- Comparing compression ratios and CPU cost under representative telemetry
  batches.
- Broker-level verification of compressed batch acknowledgement and replay.

## Phase 14: HTTP-To-Redpanda Runtime Smoke Test

### Intention

Prove the first bounded runtime path from the public HTTP adapter through the
Kafka publisher into Redpanda, without treating process readiness as durable
delivery evidence.

### Behavior

`./scripts/smoke-local-ingestor.sh` creates one fixture, submits it twice, and
consumes the newest broker record. The expected result is one `202` with a
queue offset, one `200` duplicate response with no second publish, and one
matching broker record.

### Implementation

- `scripts/local-stack.sh exec` provides non-interactive container diagnostics
  while keeping runtime identification on `stderr`.
- `scripts/smoke-local-ingestor.sh` generates a bounded fixture, validates both
  HTTP responses, and parses Redpanda's multiline JSON output from a temporary
  file rather than passing payloads through process arguments.
- `docs/operations/local-stack.md` and
  `docs/operations/ingestor-service.md` document the command and evidence
  boundary.

### Situations Evaluated

- Producer acknowledgement returns an HTTP `202` and a Redpanda offset.
- An exact repeated request returns `200 duplicate` and does not publish again.
- The broker contains the matching idempotency key.
- The test avoids asserting that a duplicate response repeats the original
  queue offset; that is not part of the HTTP contract.
- Large broker output is handled through a temporary file to avoid operating
  system argument-size limits.

### Evidence

The first successful run produced:

- HTTP first publish: `202`, `nvt.telemetry.raw.v1:0:4`.
- HTTP duplicate: `200`, `duplicate`.
- Broker delivery: topic `nvt.telemetry.raw.v1`, matching record.

### Deliberately Deferred

- Restart persistence, retention, replay completeness, throughput, backpressure,
  dead-letter handling, and multi-record ordering.

## Phase 15: Redpanda Restart And Replay Check

### Intention

Verify that a broker-acknowledged record remains readable from its original
partition and offset after recreating the Redpanda container with its named
volume preserved.

### Behavior

`./scripts/verify-redpanda-replay.sh` publishes one unique fixture, extracts
the returned topic/partition/offset, restarts Redpanda, and consumes from that
exact offset. The test passes only when the topic and idempotency key match.

### Implementation

- `scripts/verify-redpanda-replay.sh` owns the publish, restart, and exact-offset
  replay sequence.
- `scripts/local-stack.sh exec` keeps the `rpk` output isolated from wrapper
  diagnostics.
- The `stack-replay` mise task and operations documentation provide the
  repeatable entry point.

### Situations Evaluated

- Broker acknowledgement supplies a concrete replay coordinate.
- Container recreation does not remove the named Redpanda data volume.
- Replay validates identity without printing payload contents.
- `rpk` partition and offset are passed as separate flags; its `partition:offset`
  range syntax can otherwise start at the partition's beginning.
- The Podman-backed Compose health discrepancy was resolved by using the
  explicit `CMD-SHELL` form for the Python readiness check; all services then
  reported healthy after recreation.

## Phase 16: Bounded Redpanda Retention Check

### Intention

Verify the broker's time-based deletion mechanism on an isolated temporary
topic before making any claim about application-topic retention.

### Behavior

`./scripts/verify-redpanda-retention.sh` creates a one-partition topic with
`retention.ms=5000`, `segment.ms=1000`, and `segment.bytes=16384`, produces
three probe records to force segment rollover, verifies the initial watermark,
waits for cleanup, and requires the log start offset to advance. The temporary
topic is deleted by the exit trap.

### Implementation

- `scripts/verify-redpanda-retention.sh` owns topic creation, production,
  offset inspection, expiry wait, and cleanup.
- `mise run stack-retention` exposes the repeatable entry point.
- Operations documentation distinguishes this broker configuration check from
  application-topic and production retention claims.

### Situations Evaluated

- Retention configuration is applied at topic creation.
- Segment closure is forced on a short interval so expiry can be observed.
- A second record is appended after the segment interval because retention
  applies to closed segments, not the active segment.
- The second record also exceeds the configured segment size, forcing a
  size-based rollover when time-based rollover was insufficient in the local
  Redpanda runtime.
- A third record closes the segment containing the rollover record; the test
  only requires the first segment's start offset to advance, leaving the final
  active segment outside the expiry assertion.
- On Redpanda `v24.3.6`, the configured topic retained all records after the
  bounded 75-second wait. The script reports exit `2` for this capability result
  rather than converting it into a false pass.
- Cleanup is isolated to a uniquely named temporary topic.

### Deliberately Deferred

- Application-topic retention policy selection, legal immutability, remote tier
  retention, and retention behavior under sustained load.

## Phase 17: Redpanda Retention Version A/B

### Intention

Determine whether the retention result is specific to the pinned broker version
without risking the existing local Redpanda volume.

### Behavior

The baseline `v24.3.6` test was repeated with `v25.3.17` on a fresh named
volume using the same topic configuration and fixture. Both versions accepted
the configuration but left `log_start_offset=0` after the bounded wait.

### Implementation

- `REDPANDA_DATA_VOLUME` makes the Compose Redpanda volume selectable for
  isolated experiments while preserving `nvt_redpanda_data` by default.
- The candidate version was started only with the Redpanda service; the
  application stack was restored to the baseline after the test.
- No image change was published because the A/B result did not justify one.

### Situations Evaluated

- Directly opening the existing v24 volume with v25 was rejected by Redpanda's
  incompatible logical-version guard; this is an invalid upgrade path.
- A fresh v25 volume removed the migration variable but reproduced the retention
  non-observation.
- The baseline v24 stack was restored and its existing volume preserved.

### Decision

Keep `redpandadata/redpanda:v24.3.6` pinned for now. The evidence does not
justify replacing it; retention remains an unresolved local capability result
and must not be claimed as verified.

### Deliberately Deferred

- Direct segment inspection, broker debug logging, alternative retention
  properties, and a production-version selection.

## Phase 10: Local Compose Service Stack

### Intention

Provide one Docker/Podman-compatible local service definition for the queue,
raw object store, analytical store, and catalog. The definition must be easy to
validate before startup and must preserve data through normal local restarts.

### Behavior

`./scripts/local-stack.sh` selects Docker Compose or Podman Compose, validates
the interpolated configuration, and manages the four declared services. Named
volumes persist local service data. Normal `down` does not remove volumes;
`reset` is destructive and requires explicit confirmation.

The ingestor application is intentionally not represented by a placeholder
container. Its service belongs in the stack after its HTTP adapter and real
durable publisher adapter exist, otherwise the local stack would overstate its
acceptance and durability behavior.

### Implementation

- `deploy/local/compose.yaml` defines pinned images, ports, named volumes,
  network, environment interpolation, and service healthchecks where supported.
- `deploy/local/.env.example` provides local-only placeholders.
- `scripts/local-stack.sh` provides the runtime-neutral lifecycle entry point.
- `docs/operations/local-stack.md` defines usage, safety, expected results,
  failure interpretation, and evidence.
- No application or domain module depends on Docker, Podman, or any service
  hostname.

### Situations Evaluated

- Docker Compose available.
- Podman Compose available without Docker.
- Neither runtime available.
- Configuration validation without starting services.
- Normal stop while preserving named volumes.
- Explicit destructive reset requiring confirmation.
- Service health versus actual durability or compatibility evidence.
- RustFS non-root volume ownership requirements.
- Local placeholder credentials versus production secrets.

### Deliberately Deferred

- Starting services in the current environment without explicit operational
  smoke-test authorization.
- Ingestor application container until its real HTTP and durable-publisher
  adapters exist.
- Broker restart/replay and S3 compatibility claims.
- Digest locking and higher-environment deployment roots.

## Phase 9: Embedded Analytics Compatibility Fixture

### Intention

Measure whether DuckDB and chDB can reproduce a small analytical result without
coupling application logic to either engine. This is a compatibility gate, not
an engine benchmark or a production storage decision.

### Behavior

The fixture computes deterministic per-signal count, minimum, maximum, and
average values. The reference adapter always runs. DuckDB and chDB adapters run
only when their optional packages are installed. Missing packages produce exit
status `2`, while a result mismatch produces exit status `1`.

### Implementation

- `analytics_contract/ports.py` defines the small application-facing query port.
- `analytics_contract/fixture.py` defines canonical observations and expected
  summaries.
- `analytics_contract/reference.py` provides a dependency-free expectation.
- `analytics_contract/duckdb_adapter.py` and `analytics_contract/chdb_adapter.py`
  contain optional infrastructure adapters.
- `analytics_contract/verify.py` compares all available adapters.
- `scripts/verify-analytics-compatibility.sh` and its operations document make
  the capability result repeatable.
- No engine dependency is forced into the base runtime.

### Situations Evaluated

- Stable reference aggregation.
- DuckDB SQL result parity when installed.
- chDB SQL result parity when installed.
- Optional dependency unavailable.
- Adapter result mismatch.
- Engine-specific setup isolated from the shared query port.

### Deliberately Deferred

- Performance and cost claims.
- Parquet/object-store scans.
- ClickHouse server parity.
- Concurrent writes, restart durability, and cloud behavior.

### Next Gate

Install and verify each optional engine in a controlled benchmark environment,
then add the local Redpanda/Compose adapter separately. Do not interpret exit
status `2` as evidence that an engine is compatible.

The existing working tree contains unrelated untracked material and an
unstaged TODO edit in `telemetry_contract/generator.py`; those items are not
part of the completed phases and must remain outside future commits until their
ownership is clear.

## Phase 8: Embedded Analytics Evaluation

### Intention

Evaluate DuckDB and chDB for notebook development and demos without weakening
the production ingestion contract. The evaluation exists because an embedded
analytics engine can shorten the feedback loop, but it can also create a false
impression that local persistence, SQL compatibility, and production durability
are the same property.

### Behavior

The recommendation is to use DuckDB by default for lightweight development and
Parquet-oriented notebook work, and chDB when ClickHouse SQL behavior is the
primary compatibility objective. A real ClickHouse service remains the choice
when a demo requires a network endpoint or multiple independent processes.

The requested operating levels were four, so the evaluation defines separate
development, demo, quiet-production, and high-volume-production profiles.

### Implementation

- `docs/research/embedded-analytics-options.md` records engine capabilities,
  compatibility-layer costs, stack compositions, migration rules, situations
  evaluated, and source-backed recommendations.
- No runtime dependency was added yet; this phase is an architecture and
  compatibility decision before benchmarking.

### Situations Evaluated

- Fast notebook acquisition with no service startup.
- ClickHouse-compatible SQL in a self-contained demo.
- Networked dashboard access and multi-process readers.
- Single-writer limitations of embedded database files.
- Quiet production where fixed broker cost may dominate traffic cost.
- High-volume production requiring replay, consumer isolation, and durable raw
  recovery.
- Compatibility of envelopes, Parquet/Arrow, curated tables, SQL, and service
  APIs across environments.

### Deliberately Deferred

- Selecting a final vendor or managed cloud service.
- Claiming performance or cost without a controlled benchmark.
- Using DuckDB or chDB as the authoritative raw-ingestion store.
- Emulating a ClickHouse server API over an embedded engine.

### Next Gate

Create one measured compatibility fixture that runs the same generated data and
representative queries through DuckDB, chDB, and the selected ClickHouse
service. Record versions, hardware, dataset shape, query text, result parity,
memory, startup, disk, and restart behavior.
