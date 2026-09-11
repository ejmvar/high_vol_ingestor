# Local Service Stack

## Intention

Run the local platform services through one Compose-compatible definition. The
same file is intended for Docker Compose, `podman compose`, and
`podman-compose`; the lifecycle script selects an available runtime without
changing service or application contracts.

## Services

| Service | Local role | Published ports | Persistent volume |
| --- | --- | --- | --- |
| Ingestor | HTTP-to-Kafka telemetry ingress | `8080` | None; broker and raw sinks own persistence |
| Redpanda | Kafka-compatible durable queue candidate | `19092`, `19644`, `18081`, `18082` | `nvt_redpanda_data` |
| RustFS | S3-compatible raw-object store candidate | `9000`, `9001` | `nvt_rustfs_data`, `nvt_rustfs_logs` |
| ClickHouse | Curated values, aggregates, and features | `8123`, `9009` | `nvt_clickhouse_data`, `nvt_clickhouse_logs` |
| PostgreSQL | Catalog, lineage, schema, and retention metadata | `5432` | `nvt_postgres_data` |

The ingestor application is built from `deploy/local/Dockerfile.ingestor` and
publishes to the internal Redpanda address. Its container healthcheck proves
HTTP readiness only; it does not prove that Redpanda has accepted a record.

## Quick Path

```bash
./scripts/local-stack.sh config
./scripts/local-stack.sh build
./scripts/local-stack.sh up
./scripts/local-stack.sh ps
```

The default environment file contains local-only placeholder credentials. Use
`LOCAL_STACK_ENV_FILE=/path/to/local.env` for a private local override; never
commit that override. If the default host port is already occupied, set
`REDPANDA_EXTERNAL_PORT` in the environment or private override file; the
container keeps its internal Kafka listener on `19092`.
For isolated broker experiments, set `REDPANDA_DATA_VOLUME` to a temporary
named volume; normal operation keeps `nvt_redpanda_data`.

## Runtime Selection

The script prefers `docker compose`, then `podman compose`, then
`podman-compose`. It uses only Compose-compatible service, volume, network,
environment, port, and healthcheck constructs. `x-podman` extensions are not
required by the stack definition.

## Expected Results

- `config` validates interpolation without starting containers.
- `build` builds local application images without starting containers.
- `up` starts the four declared services with named persistent volumes.
- `restart SERVICE` recreates one service without removing named volumes.
- `exec SERVICE COMMAND...` runs a non-interactive diagnostic command inside a
  service container.
- `ps` reports service state and health where the image provides a healthcheck.
- `down` stops and removes containers but preserves named volumes.
- `reset` removes containers and volumes only when
  `CONFIRM_LOCAL_RESET=YES` is explicitly set.

## Safety and Side Effects

- This is a local development stack, not a production deployment.
- Images are pinned by tag and must be reviewed and digest-pinned before a
  higher-trust environment.
- Named volumes persist data across normal `down`/`up` cycles.
- Reset is destructive to local service data.
- Credentials are local placeholders and must never be reused in production.
- A healthy container proves process readiness only, not S3 compatibility,
  queue durability, data retention, or cloud equivalence.
- The ingestor health endpoint does not perform a broker round-trip.

## Failure Interpretation

- Missing Docker/Podman Compose is a tooling-capability result.
- Config failure is a definition or interpolation error.
- Container startup failure is an image, permission, resource, or runtime issue.
- Unhealthy service requires service-specific diagnosis; do not bypass the
  health gate by relabeling the service.
- Passing `config` does not prove that images can be pulled or services can
  communicate.
- A host-port bind failure is an environment collision; use
  `REDPANDA_EXTERNAL_PORT` rather than changing the container listener.

## End-To-End Smoke Test

With the stack running, execute:

```bash
REDPANDA_EXTERNAL_PORT=29092 ./scripts/smoke-local-ingestor.sh
```

The script submits one deterministic fixture, repeats the same request, and
consumes one record from the configured Redpanda topic. A passing result proves
HTTP acceptance, duplicate suppression, producer acknowledgement, and broker
delivery for that single record. It does not prove restart persistence,
retention, replay completeness, throughput, or production durability.

To verify one record survives a Redpanda restart and remains readable from its
original offset:

```bash
REDPANDA_EXTERNAL_PORT=29092 ./scripts/verify-redpanda-replay.sh
```

This recreates only the Redpanda container and preserves its named volume. It
is a bounded restart/replay check, not proof of retention policy or complete
log recovery.

To verify time-based retention without touching the telemetry topic:

```bash
./scripts/verify-redpanda-retention.sh
```

The script creates a temporary topic with five-second retention, one-second
segments, and a 16 KiB segment size. It produces a second record large enough
to force rollover and a third record to close the next segment, verifies the
topic configuration, waits up to 75 seconds for the background cleanup cycle,
and checks the log offsets before deleting the temporary topic. This is a local
configuration check, not a production retention or legal immutability claim.
It waits for Redpanda cluster health before creating the topic.
Exit `2` means the broker accepted the retention configuration but did not
provide deletion evidence in the bounded wait; treat that as an environment
capability result requiring investigation, not as a passing retention test.

## Verification Evidence

The lifecycle script prints the selected runtime, action, and Compose output.
It does not print secret values. Record service versions, image digests, health,
and the scope of any smoke test separately from this configuration check.

## References

- Compose Specification: https://compose-spec.io/
- Docker Compose configuration: https://docs.docker.com/reference/cli/docker/compose/config/
- Podman Compose compatibility: https://github.com/containers/podman-compose/blob/main/docs/Extensions.md
- RustFS Docker quick start: https://github.com/rustfs/rustfs#docker-quick-start
