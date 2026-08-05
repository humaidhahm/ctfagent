# memory

`memory` is a NestJS service that exposes picoCTF writeups and bounded web references through an MCP-compatible HTTP endpoint at `/mcp`. It stores the canonical CSV writeups and the supplied `picoCTF` repository documentation in PostgreSQL.

## What is included

- **525 writeups** from `../../../picoctf_writeups_real.csv`.
- **45 Markdown source documents** from `../../../github_trees/picoCTF__picoCTF.tar.gz`. The archive contains picoCTF repository documentation, not challenge writeups, so these records are kept in `source_documents` and are never merged over CSV writeups.
- PostgreSQL full-text search over challenge name, domain, and Markdown.
- MCP JSON-RPC methods `initialize`, `tools/list`, and `tools/call`.
- Six MCP tools: writeup search/retrieval, domain counts, source-document search/retrieval, and cached web-reference fetches.
- Loopback-only Docker port binding and a named Postgres volume.
- Web fetch limits: HTTP(S) only, allow-listed hosts, no URL credentials, no local/private/link-local IP literals, request timeout, response byte cap, and database-backed TTL cache.
- Optional bearer-token authentication for all non-health routes and explicit CORS allow-listing.

## Architecture

```text
Apps / agents
     |
     | MCP JSON-RPC or convenience REST routes
     v
NestJS /mcp controller
     |                 \
     v                  v
WriteupsService     WebReferenceService
     |                  |
     +---------> PostgreSQL <---------+
             writeups
          source_documents
          web_references
```

### Data model

- `writeups`: one row per CSV row. `source_key` is `csv:<row ordinal>:<challenge name>`, preserving duplicate URLs and exact challenge casing. Markdown is stored losslessly. `metadata` contains input path, row ordinal, and SHA-256 content hash.
- `source_documents`: one row per Markdown member in the picoCTF archive. `source_key` is `archive:<member path>`; archive metadata includes member path and SHA-256 hash.
- `web_references`: cached response body and metadata keyed by normalized URL.

## Run locally

Prerequisites: Bun 1.3+, and Docker Desktop with the Linux engine running. Node.js 20+ remains supported through the `start:node` fallback.

1. Copy `.env.example` to `.env` and set `MEMORY_DB_PASSWORD` in the Compose
   environment (or set `DATABASE_URL` to the matching password for a native
   process). The checked-in default is only for local development.
2. Start the database. The existing workstation already uses host port 5432, so this service deliberately binds the new container to loopback port **5434**:

   ```powershell
   docker compose up -d memory-db
   docker inspect --format "{{.State.Health.Status}}" memory-db
   ```

   The container is named `memory-db`; the PostgreSQL database and user are both `memory`. Data persists in the `memory_memory_postgres_data` Docker volume.

3. Install dependencies and load the inputs:

   ```powershell
   bun install
   bun run db:migrate
   bun run data:import
   ```

   Import output should report `Imported 525 writeups and 45 source documents.` Re-running the importer is safe because all records use stable conflict keys.

4. Start the API:

   ```powershell
   bun run build
   bun run start
   ```

   Health: `GET http://127.0.0.1:3000/mcp`

## MCP API

### Initialize

```powershell
curl -X POST http://127.0.0.1:3000/mcp `
  -H "content-type: application/json" `
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize"}'
```

### List tools

```json
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
```

### Search writeups

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "search_writeups",
    "arguments": {"query": "buffer overflow", "domain": "Pwn", "limit": 10}
  }
}
```

Search results are paged and omit Markdown. Use `get_writeup` with the returned numeric `id` to retrieve the full writeup.

Available tools:

| Tool | Arguments | Result |
| --- | --- | --- |
| `search_writeups` | `query`, `domain`, `difficulty`, `limit`, `offset` | Paged summaries |
| `get_writeup` | `id` | Full writeup Markdown and provenance |
| `list_domains` | none | Domain/count pairs |
| `search_source_documents` | `query`, `limit`, `offset` | Paged archive-document summaries |
| `get_source_document` | `id` | Full archive Markdown |
| `fetch_web_reference` | `url` | Bounded, cached remote response |

MCP tool text is capped at 128 KiB. Direct retrieved records retain their stored Markdown; clients should page search results and request full records individually.

### Convenience routes

- `GET /mcp` — health response.
- `GET /mcp/writeups?query=&domain=&difficulty=&limit=&offset=` — paged writeup summaries.
- `GET /mcp/writeups/:id` — full writeup by numeric id.
- `POST /mcp/references` with `{ "url": "https://..." }` — fetch/cache a web reference.

## Configuration

| `PORT` | `3000` | API listen port |
| `DATABASE_URL` | `postgres://memory:memory-local-only@127.0.0.1:5434/memory` | PostgreSQL connection |
| `CSV_PATH` | `../../../picoctf_writeups_real.csv` | Canonical CSV path, relative to the project directory |
| `PICOCTF_ARCHIVE_PATH` | `../../../github_trees/picoCTF__picoCTF.tar.gz` | Archive path, relative to the project directory |
| `WEB_ALLOWED_HOSTS` | `raw.githubusercontent.com,github.com,medium.com` | Comma-separated host suffix allow-list |
| `WEB_CACHE_TTL_SECONDS` | `3600` | Cache lifetime |
| `WEB_FETCH_TIMEOUT_MS` | `10000` | Remote request timeout |
| `WEB_MAX_BYTES` | `1048576` | Maximum response body size |
| `WEB_MAX_CACHE_ROWS` | `1000` | Maximum retained web-reference cache rows |
| `MEMORY_API_TOKEN` | empty | Bearer token for MCP and convenience routes; health stays public |
| `MEMORY_REQUIRE_AUTH` | `false` | Fail startup when no token is configured |
| `MEMORY_CORS_ORIGINS` | empty | Comma-separated browser origins; CORS is disabled when empty |

## Verification

```powershell
bun install
bun run build
bun test
bunx tsc --noEmit
bun run db:migrate
```

The focused tests cover MCP initialization/tool delegation, invalid tool handling, and web URL safety checks. The verified local database contains 525 `writeups` rows, 45 `source_documents` rows, and cached web references after a successful fetch.
## Production hardening

- Replace the local password and keep it outside source control.
- Set `MEMORY_API_TOKEN` to a high-entropy secret and set `MEMORY_REQUIRE_AUTH=true`; configure the same token as `MEMORY_API_TOKEN` in CTFAgent clients.
- Put the API behind TLS before exposing it beyond localhost.
- Set `MEMORY_CORS_ORIGINS` to the smallest required browser-origin set.
- Set `WEB_ALLOWED_HOSTS` to the smallest required host set.
- Keep the response cap, cache-row cap, and timeout enabled; do not turn web fetching into an unrestricted proxy.
- Add a reverse proxy rate limit and request logging before multi-tenant use.
