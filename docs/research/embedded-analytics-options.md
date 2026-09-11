# Embedded Analytics Options and Stack Profiles

Status: architecture recommendation for review

Date: 2026-09-11

## Decision Summary

Use **DuckDB as the default notebook and lightweight development engine** and
keep **chDB as the ClickHouse-compatibility option** for demos or investigations
that must exercise ClickHouse SQL behavior without running a ClickHouse
server. Do not make either embedded engine the authoritative raw-ingestion
boundary.

The repository requirements list four operating levels, so this document
defines four profiles:

1. Development: DuckDB plus local files and the existing pure Python boundary.
2. Demo: chDB or a single ClickHouse server, selected by dashboard needs.
3. Production quiet ingestion: durable object storage plus a small managed or
   single-node analytical service, with a low-cost queue only when buffering is
   required.
4. Production high volume: durable Kafka-compatible streaming, object storage,
   and horizontally scalable ClickHouse or an equivalent analytical service.

The compatibility strategy is to keep the envelope, raw object layout,
Parquet/Arrow interchange, catalog metadata, and query-service API stable. SQL
should be treated as an adapter concern rather than the cross-environment
contract.

## What the Engines Actually Provide

### DuckDB

DuckDB is an in-process analytical database with a persistent local database
file option. It can query Parquet directly, including multiple files through a
glob, and can stream/filter columnar data without first importing it into a
server database. This makes it particularly suitable for notebooks, fixture
inspection, local feature computation, and small demos.

The important operational boundary is concurrency: DuckDB supports multiple
writer threads within one process, but a database file is not a general
multi-process write service. Multiple processes can read a file in read-only
mode. Therefore, a DuckDB file should be owned by one writer process or treated
as a read-only artifact after creation.

DuckDB can access cloud/object storage through its HTTP/S3 facilities, but that
does not turn a local DuckDB file into a distributed transactional database.
Credentials, object consistency, concurrent writers, and lifecycle behavior
remain deployment responsibilities.

### chDB

chDB is an in-process SQL OLAP engine powered by ClickHouse. Its Python API can
run in memory or use a persistent session directory. The documented session API
supports creating tables, inserting rows, and querying state across calls; a
persistent session can survive process restarts when its directory is retained.
It also reads and writes common analytical formats such as Parquet, CSV, JSON,
Arrow, and ORC.

chDB is attractive when the demo must exercise ClickHouse-oriented SQL,
MergeTree table definitions, functions, or result behavior without a server.
It is not a drop-in ClickHouse server: there is no network endpoint, external
authentication boundary, cluster coordination, server-level observability, or
automatic high-availability behavior. A persistent local session is still a
process-owned local database directory.

### Neither Engine Is the Raw System of Record

Both engines are analytical consumers or local projection targets. The raw
payload remains authoritative in append-only object storage with checksums,
sequence numbers, schema versions, idempotency keys, and lineage. This keeps
notebook or demo engine replacement from changing capture semantics.

## Compatibility-Layer Cost

Compatibility has several independent dimensions. Treating “supports SQL” as
full compatibility would hide the most expensive risks.

| Boundary | DuckDB cost | chDB cost | Recommendation |
| --- | --- | --- | --- |
| Envelope and identity | Low | Low | Share the v1 envelope and validator unchanged |
| Raw bytes and object layout | Low | Low | Share checksums, object keys, and Parquet/Arrow conventions |
| Basic relational SQL | Low | Very low | Keep queries simple and versioned |
| Advanced SQL/functions | Medium-high | Low-medium | Use engine-specific adapters and capability tests |
| Table DDL and types | Medium | Low-medium | Generate per-engine DDL; do not share DDL blindly |
| Python notebook API | Low | Low-medium | DuckDB is familiar; chDB offers ClickHouse/DataStore paths |
| Multi-process writes | Not suitable | Not suitable | Put a service or queue in front of writes |
| Network/auth/HA/monitoring | High if emulated | High if emulated | Use the real service at the environment boundary |
| Migration to ClickHouse server | Medium-high | Low-medium | chDB minimizes SQL semantic drift, not operations drift |
| Packaging footprint | Low-medium | Medium-high | Validate platform wheels, CPU, and startup time in CI |

### Cost Interpretation

The layer is cheap when it consists of:

- one canonical envelope and raw object layout;
- a narrow curated relational model;
- Parquet or Arrow interchange;
- a small query repository with capability-tested queries;
- an API that returns domain-level results instead of engine-specific objects.

The layer becomes expensive when it tries to emulate a ClickHouse server over
DuckDB or chDB. That would require replacing network access, authentication,
concurrency, retries, server settings, system tables, observability, cluster
behavior, and operational failure handling. Do not build that emulation layer.

### Recommended Adapter Shape

Keep three ports separate:

- `DurablePublisher`: accepts validated envelopes and returns an acceptance
  offset.
- `RawObjectWriter`: writes exact payload bytes and returns object identity and
  checksum evidence.
- `AnalyticsReader`/`AnalyticsWriter`: creates curated projections and serves
  queries through an engine-specific implementation.

The current `IngestionEndpoint` already establishes the first boundary. The
engine adapter should consume replayable raw data rather than become the first
place where raw data is accepted.

## Four Stack Profiles

### Profile 1: Development

**Goal:** light setup, fast acquisition, immediate notebook feedback.

| Component | Composition |
| --- | --- |
| Producer | Deterministic Python generators and the pure ingestion boundary |
| Queue | In-memory publisher for unit tests; no broker by default |
| Raw | Local append-only files or Parquet fixtures with checksum sidecars |
| Analytics | DuckDB in-memory or one local `.duckdb` file |
| Metadata | JSON/YAML fixtures initially; SQLite/DuckDB catalog only for local experiments |
| Dashboard | Notebook, local script, or a thin API over query results |
| Verification | Contract tests, deterministic replay tests, and bounded one-hour fixture runs |

**Why:** This path has the fewest processes and fastest acquisition loop. The
producer and envelope behavior stay identical to later profiles, while the
queue and analytics engine are replaceable doubles.

**Limit:** It proves correctness and developer ergonomics, not queue durability,
multi-process access, network failure recovery, or production throughput.

**Compatibility cost:** Low. The only required discipline is to query curated
tables through a small repository and keep raw fixtures in portable formats.

### Profile 2: Demo

**Goal:** stable and repeatable demonstration without unnecessary infrastructure
cost.

#### Demo A: Notebook-First

| Component | Composition |
| --- | --- |
| Producer | Python generator plus bounded stream |
| Queue | In-memory or single local Redpanda only when queue behavior is part of the demo |
| Raw | Local S3-compatible store or versioned fixture directory |
| Analytics | chDB persistent session directory |
| Metadata | Small PostgreSQL/SQLite-compatible catalog, or a chDB catalog for a self-contained demo |
| Dashboard | Notebook or application process using chDB directly |

Choose this when the audience needs ClickHouse SQL behavior and the demo does
not require a separately reachable database endpoint.

#### Demo B: Service-First

| Component | Composition |
| --- | --- |
| Producer | Python generator plus ingestion endpoint |
| Queue | Single Redpanda container with explicitly configured persistence |
| Raw | RustFS through the S3 API |
| Analytics | Single-node ClickHouse container |
| Metadata | PostgreSQL/TimescaleDB catalog |
| Dashboard | Separate dashboard/API process using ClickHouse client protocol |

Choose this when the dashboard, multiple processes, or an external reviewer
must connect to the analytical service. It is heavier than chDB but removes the
largest demo-only compatibility gap.

**Recommendation:** Use Demo A for notebook demonstrations and Demo B for an
end-to-end ingestion demonstration. Do not pretend they have identical
availability or durability semantics.

### Profile 3: Production Quiet Data Ingestion

**Goal:** stable, cheap, durable ingestion for low event rates and modest
concurrency.

| Component | Composition |
| --- | --- |
| Edge | Local buffering, feature extraction, and bounded retries |
| Acceptance | Managed HTTPS ingestion or a small Kafka-compatible broker when outage buffering requires it |
| Raw | Managed versioned object storage with retention and object-lock policy where required |
| Analytics | Small managed ClickHouse/analytical service, or one controlled ClickHouse node for non-critical workloads |
| Metadata | Managed PostgreSQL for asset, sensor, schema, lineage, and retention state |
| Dashboard | API/query service; clients do not connect directly to embedded engines |
| Operations | Backups, access control, alerting, queue/object-store health, and replay runbooks |

For truly quiet traffic, a direct durable object-storage acceptance path can be
cheaper than operating a broker, provided the endpoint can provide the required
acceptance semantics, idempotency, bounded retries, and outage behavior. If the
system needs decoupled consumers, replay windows, or burst absorption, retain a
managed Kafka-compatible queue even when average traffic is low.

**Recommendation:** Do not introduce chDB or DuckDB into the production
acceptance path. They may be used by offline analysts against copied raw or
curated data.

### Profile 4: Production High Volume

**Goal:** durable high-rate capture, consumer isolation, replay, and scalable
analytical serving.

| Component | Composition |
| --- | --- |
| Edge | High-rate acquisition, deterministic preprocessing, local durable buffer |
| Queue | Managed Kafka-compatible service or multi-node Redpanda/Kafka with replication and tested acknowledgements |
| Raw | Managed object storage, append-only partitions, checksums, versioning, lifecycle, and independent recovery |
| Analytics | ClickHouse cluster or managed ClickHouse with partitioning, replicas, and resource controls |
| Metadata | Managed PostgreSQL plus schema/catalog/lineage tables |
| Derived data | Replayable consumers for curated values, aggregates, and features |
| Observability | Queue lag, rejected records, DLQ, raw-sink success, processing latency, storage errors, and stale-dashboard indicators |

DuckDB remains useful for sampled extracts, offline validation, and analyst
notebooks. chDB remains useful for ClickHouse-compatible local reproductions.
Neither should receive the high-volume production stream directly.

## Migration Rules Across Profiles

The following must remain stable:

- v1 envelope fields and semantic validation rules;
- producer sequence and idempotency behavior;
- raw payload checksum and byte-length meaning;
- raw object identity and lineage references;
- curated column meanings and units;
- feature definition and processing-version identifiers;
- retention state and deletion audit records;
- query-service response contracts used by dashboards.

The following may vary by profile:

- queue implementation and topic partition count;
- object-store endpoint and authentication adapter;
- analytics engine and SQL dialect;
- batching, compression, and materialization timing;
- dashboard deployment and query caching;
- infrastructure topology and capacity.

## Situations Evaluated

- A developer needs to acquire data immediately without starting five services.
- A notebook must inspect Parquet files larger than memory.
- A demo must use ClickHouse SQL without a ClickHouse server.
- A dashboard needs a network endpoint and multiple concurrent readers.
- An embedded database file is accessed by more than one writer process.
- A publisher fails after validation but before acceptance.
- Low-rate production traffic needs durable storage but not a large streaming cluster.
- High-volume production needs consumer isolation, replay, and independent raw recovery.
- An attempt is made to use an embedded engine as a distributed HA service.
- A migration changes SQL syntax while the envelope and raw lineage remain stable.

## Recommendation Matrix

| Level | Default analytics choice | Queue | Raw authority | Main reason |
| --- | --- | --- | --- | --- |
| Development | DuckDB | In-memory | Local files/Parquet | Lowest setup and fastest feedback |
| Demo notebook | chDB | In-memory or bounded local broker | Local S3-compatible files | ClickHouse behavior without server overhead |
| Demo service | ClickHouse single node | Single Redpanda | RustFS/S3 | Real networked service path |
| Production quiet | Managed/small ClickHouse | Direct durable object acceptance or small managed queue | Managed object storage | Minimize fixed infrastructure while preserving durability |
| Production high volume | Managed/clustered ClickHouse | Replicated Kafka-compatible service | Managed object storage | Replay, isolation, scale, and recovery |

## Verification Plan Before Adoption

The next benchmark should use the same generated envelopes and raw payloads in
DuckDB, chDB, and the selected ClickHouse service. Compare:

- schema and type mapping;
- row counts and checksum/lineage preservation;
- aggregate values and null/quality behavior;
- timestamp and timezone behavior;
- representative feature queries;
- startup and import time;
- memory and disk footprint;
- concurrent reader behavior;
- restart and recovery behavior for persistent profiles.

Do not use vendor benchmark tables as a capacity commitment. Record exact
versions, hardware, dataset shape, query text, and measured results.

## Source Register

Accessed 2026-09-11.

| Source | Evidence used |
| --- | --- |
| DuckDB concurrency: https://duckdb.org/docs/current/connect/concurrency | One-process read/write model, multiple writer threads within one process, and read-only multi-process access |
| DuckDB Python DB API: https://duckdb.org/docs/current/clients/python/dbapi | In-memory and persistent file connections, including read-only mode |
| DuckDB Parquet guide: https://duckdb.org/docs/current/data/parquet/overview | Direct Parquet querying and columnar analytical workflow |
| DuckDB Jupyter/cloud guidance: https://github.com/duckdb/duckdb-web/blob/main/docs/current/guides/python/jupyter.md | HTTPFS/object-storage access pattern |
| chDB documentation: https://clickhouse.com/docs/chdb | In-process ClickHouse engine, formats, Python integration, and no-server positioning |
| chDB API reference: https://github.com/chdb-io/chdb/blob/main/agent/skills/chdb-sql/references/api-reference.md | In-memory and persistent sessions, state, queries, and lifecycle |
| chDB ClickHouse-local guide: https://clickhouse.com/docs/chdb/guides/clickhouse-local | Persistent local database directory and interaction with ClickHouse-local data |

## Decision Status

Recommended for adoption in the next design step, pending a measured
DuckDB/chDB/ClickHouse compatibility fixture. The recommendation does not
change the existing raw, queue, catalog, or durability boundaries.
