# Local Ingestor Service

## Intention

Run the provider-neutral ingestion boundary as a local HTTP service and connect
it to the Kafka-compatible Redpanda adapter without leaking HTTP or Kafka types
into the telemetry contract package.

## Usage

Start the local stack through the canonical lifecycle script:

```bash
./scripts/local-stack.sh up
```

Install and verify the host-side Kafka adapter dependencies with:

```bash
mise run kafka-sync
```

Check process readiness:

```bash
curl --fail http://localhost:8080/health
```

## Request Contract

`POST /v1/telemetry/chunks` accepts JSON with:

- `envelope`: the v1 telemetry envelope object;
- `payload_base64`: the exact binary payload encoded as base64.

The adapter decodes the payload, calls `IngestionEndpoint`, and returns the
queue acceptance offset only after the Kafka publisher future resolves.

## Response Behavior

| Condition | HTTP status | Meaning |
| --- | --- | --- |
| New record accepted by publisher | `202` | Queue acceptance returned |
| Exact idempotent duplicate | `200` | No second publish performed |
| Invalid JSON, envelope, or payload encoding | `400` | Rejected before publish |
| Publisher or broker failure | `503` | Retry may be attempted |
| Unknown route | `404` | No operation performed |

`GET /health` returns `{"status":"ready"}`. It is a process-readiness check;
it does not perform a broker round-trip.

## Environment

| Variable | Default in container | Purpose |
| --- | --- | --- |
| `INGESTOR_HOST` | `0.0.0.0` | HTTP bind address |
| `INGESTOR_PORT` | `8080` | HTTP port |
| `KAFKA_BOOTSTRAP_SERVERS` | `redpanda:9092` | Internal Kafka endpoint |
| `KAFKA_TOPIC` | `nvt.telemetry.raw.v1` | Raw telemetry topic |

These defaults are local-development values. Production authentication, TLS,
network policy, and secret injection are separate adapter concerns.

## Safety and Side Effects

- The local service binds a host port and publishes to the local Redpanda
  service.
- The request body is bounded by `16 MiB` before decoding.
- Request bodies and payloads are not written to ordinary access logs.
- The local Dockerfile installs pinned `kafka-python` and `zstandard` versions;
  Zstandard is required by the publisher's configured compression.
- Container startup does not prove durable acknowledgement until a broker
  smoke test verifies it.

## Issue And Decision Log

### Missing Zstandard Codec

The Kafka adapter selects `compression_type="zstd"`. `kafka-python` treats the
Zstandard implementation as an optional dependency, so an image containing
only `kafka-python` fails during producer construction with
`Libraries for zstd compression codec not found`.

Decision: keep Zstandard for high-volume batches and pin both Kafka runtime
packages in the `kafka` optional extra in `pyproject.toml`. `uv.lock`, `mise run
kafka-sync`, and the local Dockerfile provide reproducible host and container
installation paths.
Switching compression off would avoid the dependency but would increase
network and broker storage costs; it is not the selected default.

## Failure Interpretation

- `400` is a caller contract failure and must not be retried unchanged.
- `503` is a bounded publisher failure; retry behavior belongs to the producer
  and must preserve the same idempotency key.
- A healthy `/health` response with `503` ingestion indicates broker or
  publisher unavailability, not an HTTP process failure.
- A successful `202` is local adapter behavior until broker persistence and
  replay are verified by the infrastructure test suite.

## Verification Evidence

The unit suite covers the HTTP mapping and injected publisher behavior. The
remaining runtime evidence must come from the local stack smoke-test script and
must record service identity, broker acceptance, duplicate delivery, restart,
retention, and replay without secrets.

The bounded first-stage check is:

```bash
REDPANDA_EXTERNAL_PORT=29092 ./scripts/smoke-local-ingestor.sh
```

It submits one deterministic fixture, repeats the exact request, and consumes
one matching record from Redpanda. Larger-volume, restart, retention, and replay
tests remain separate acceptance gates.

The restart/replay gate is:

```bash
REDPANDA_EXTERNAL_PORT=29092 ./scripts/verify-redpanda-replay.sh
```

It records the acknowledged partition and offset, recreates Redpanda without
removing its volume, and reads that exact record back from the log.
