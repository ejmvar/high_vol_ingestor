# Local Service Stack

## Intention

Run the local platform services through one Compose-compatible definition. The
same file is intended for Docker Compose, `podman compose`, and
`podman-compose`; the lifecycle script selects an available runtime without
changing service or application contracts.

## Services

| Service | Local role | Published ports | Persistent volume |
| --- | --- | --- | --- |
| Redpanda | Kafka-compatible durable queue candidate | `19092`, `19644`, `18081`, `18082` | `nvt_redpanda_data` |
| RustFS | S3-compatible raw-object store candidate | `9000`, `9001` | `nvt_rustfs_data`, `nvt_rustfs_logs` |
| ClickHouse | Curated values, aggregates, and features | `8123`, `9009` | `nvt_clickhouse_data`, `nvt_clickhouse_logs` |
| PostgreSQL | Catalog, lineage, schema, and retention metadata | `5432` | `nvt_postgres_data` |

The ingestor application is not yet a container in this stack because its HTTP
adapter and real durable publisher adapter have not been implemented. Adding a
placeholder process would falsely imply end-to-end durability.

## Quick Path

```bash
./scripts/local-stack.sh config
./scripts/local-stack.sh up
./scripts/local-stack.sh ps
```

The default environment file contains local-only placeholder credentials. Use
`LOCAL_STACK_ENV_FILE=/path/to/local.env` for a private local override; never
commit that override.

## Runtime Selection

The script prefers `docker compose`, then `podman compose`, then
`podman-compose`. It uses only Compose-compatible service, volume, network,
environment, port, and healthcheck constructs. `x-podman` extensions are not
required by the stack definition.

## Expected Results

- `config` validates interpolation without starting containers.
- `up` starts the four declared services with named persistent volumes.
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

## Failure Interpretation

- Missing Docker/Podman Compose is a tooling-capability result.
- Config failure is a definition or interpolation error.
- Container startup failure is an image, permission, resource, or runtime issue.
- Unhealthy service requires service-specific diagnosis; do not bypass the
  health gate by relabeling the service.
- Passing `config` does not prove that images can be pulled or services can
  communicate.

## Verification Evidence

The lifecycle script prints the selected runtime, action, and Compose output.
It does not print secret values. Record service versions, image digests, health,
and the scope of any smoke test separately from this configuration check.

## References

- Compose Specification: https://compose-spec.io/
- Docker Compose configuration: https://docs.docker.com/reference/cli/docker/compose/config/
- Podman Compose compatibility: https://github.com/containers/podman-compose/blob/main/docs/Extensions.md
- RustFS Docker quick start: https://github.com/rustfs/rustfs#docker-quick-start
