# Services

Services that are deployed with CTFAgent live below this directory. Each service
owns its runtime source, package manifest, and container build definition.

## `memory`

`services/memory` is the NestJS memory microservice. It exposes the MCP-compatible
HTTP API at `/mcp` and stores imported writeups, source documents, and bounded
web references in PostgreSQL.

The service has two deployment dependencies in the root Compose file:

- `memory-db`: PostgreSQL 16 with the named `memory_postgres_data` volume.
- `memory`: the NestJS process, which waits for database health, runs
  `db:migrate` and `data:import`, then starts the API.

Compose binds the memory API to `127.0.0.1:3001` and PostgreSQL to
`127.0.0.1:5434`. Containers use `http://memory:3000` and the internal
PostgreSQL service name instead. The API container reaches memory through the
same Compose network using `MEMORY_SERVICE_URL`.

The canonical import inputs are deliberately not copied into this service.
From the monorepo root they remain `../picoctf_writeups_real.csv` and
`../github_trees/picoCTF__picoCTF.tar.gz` relative to `ctfagent/`. Compose mounts
them read-only at `/app/data`; override the host paths with
`MEMORY_CSV_PATH` and `MEMORY_ARCHIVE_PATH` when using another checkout layout.
These source artifacts are never used as writable application storage.

See [`../README.md`](../README.md) for Docker Compose and local Bun commands.
