<p align="center">
<a href="https://dscvit.com">
	<img width="200" src="https://res.cloudinary.com/startup-grind/image/upload/c_fill,dpr_2.0,f_auto,g_center,h_1200,q_100,w_1200/v1/gcs/platform-data-goog/contentbuilder/GDG_Bevy_SocialSharingThumbnail_KFxxrrs.png" alt="GDG VIT"/>
</a>
	<h2 align="center">CTFAgent</h2>
	<h4 align="center">AI-powered multi-agent CTF solver that autonomously solves Capture The Flag challenges across multiple categories.</h4>


---

[![Join Us](https://img.shields.io/badge/Join%20Us-Developer%20Student%20Clubs-red)](https://gdg.community.dev/gdg-on-campus-vellore-institute-of-technology-vellore-india/)

[![DOCS](https://img.shields.io/badge/Documentation-see%20docs-green?style=flat-square&logo=appveyor)](#usage)
[![UI ](https://img.shields.io/badge/User%20Interface-CLI-orange?style=flat-square&logo=appveyor)](#usage)

## Features

- [x] **Multi-agent architecture** — specialized agents for each CTF domain, coordinated by a supervisor
- [x] **LLM-powered reasoning** — uses NVIDIA NIM API for AI reasoning with automatic model selection
- [x] **Session persistence** — maintains netcat/TCP sessions for interactive challenges
- [x] **Experience database** — learns from past solves; workflows are reused on similar challenges
- [x] **28+ built-in tools** — SQLMap, Gobuster, pwntools, binwalk, steghide, zsteg, ROPgadget, and more
- [x] **Automatic setup** — installs system tools and Python dependencies by domain
- [x] **RAG knowledge base** — category-specific hacking guides included
- [x] **Memory service** — optional writeup/reference retrieval backed by PostgreSQL and NestJS
- [x] **Docker support** — reproducible setup for macOS, Windows without WSL/Linux, and other environments where native Linux tools are inconvenient
- [x] **Interactive solve and hint modes** — solve challenges directly or receive progressive hints

<br>

## Dependencies

- Docker Desktop for macOS, Windows without WSL/Linux, and non-Debian systems
- Python 3.8+ for native Linux/WSL installs
- Linux or WSL2 for native installs
- NVIDIA NIM API key — available from [NVIDIA NIM](https://build.nvidia.com/)
- sudo access for native system-tool installation
- Docker BuildKit for the recommended Docker workflow
- For the optional memory service:
  - PostgreSQL
  - Bun for the local development workflow
  - `picoctf_writeups_real.csv`
  - `github_trees/picoCTF__picoCTF.tar.gz`

## Running

### Docker — Recommended

Use Docker if you are on macOS, on Windows without WSL2, or on a system where installing Linux CTF tools directly is inconvenient. The Docker image includes Debian/apt-based tools such as SQLMap, Gobuster, ffuf, binwalk, steghide, tshark, pwntools, ROPgadget, and zsteg.

Install Docker Desktop first, then:

```bash
git clone https://github.com/yourusername/ctfagent.git
cd ctfagent
mkdir -p data uploads
DOCKER_BUILDKIT=1 docker build -t ctfagent .
docker compose run --rm ctfagent
```

The first interactive Docker run prompts for your API keys/provider and writes configuration to `data/.env`. Compose mounts that file into the container, so the setup persists across container rebuilds and restarts.

To run the CLI again later:

```bash
docker compose run --rm ctfagent
```

To start the API:

```bash
docker compose --profile api up
```

Then open:

```text
http://localhost:8000/docs
```

The API service uses a Compose profile, so `docker compose up` by itself does not start it. Use `--profile api` for the API server.

### Memory Service — Docker

The memory service is part of the monorepo at `services/memory/`. The two canonical input artifacts intentionally remain outside `ctfagent`:

```text
cyber/
├── ctfagent/
│   ├── docker-compose.yml
│   └── services/memory/
├── picoctf_writeups_real.csv
└── github_trees/picoCTF__picoCTF.tar.gz
```

Run these commands from the `ctfagent/` directory:

```bash
cp .env.example .env
mkdir -p data
cp .env.example data/.env
# Edit .env and set MEMORY_CSV_PATH and MEMORY_ARCHIVE_PATH to real host files.
# Set MEMORY_ENABLED=true only after the memory service is running.
docker compose --profile memory up --build memory
```

On PowerShell, the equivalent commands are:

```powershell
Copy-Item .env.example .env
New-Item -ItemType Directory -Force data
Copy-Item .env.example data/.env
```

Set `MEMORY_DB_PASSWORD` in `.env` to a non-default value outside isolated development. Do not commit `.env`.

To start the complete API stack:

```bash
docker compose --profile api up --build
```

The full API stack requires both memory input files to exist. If either path is missing, Compose fails before starting the importer instead of creating empty placeholder directories.

The API reaches memory at `http://memory:3000` on the Compose network. The memory HTTP API is available from the host at `http://127.0.0.1:3001`; the API is at `http://127.0.0.1:8000`. PostgreSQL is bound only to `127.0.0.1:5434`.

Memory endpoints:

```text
GET /mcp
/mcp/writeups
/mcp/references
```

### Memory Service — Local Bun Workflow

For a local NestJS process, start only its Compose database first:

```bash
docker compose --profile memory up -d memory-db
cd services/memory
bun install
```

Set the local connection and source paths, then migrate, import, build, and start:

```bash
export DATABASE_URL='postgres://memory:memory-local-only@127.0.0.1:5434/memory'
export CSV_PATH='../../../picoctf_writeups_real.csv'
export PICOCTF_ARCHIVE_PATH='../../../github_trees/picoCTF__picoCTF.tar.gz'
bun run db:migrate
bun run data:import
bun run build
bun run start
```

On PowerShell, use `$env:DATABASE_URL`, `$env:CSV_PATH`, and `$env:PICOCTF_ARCHIVE_PATH`.

The local process listens on port `3000` by default. Stop it with `Ctrl-C`.

The CSV and archive are migration/import inputs, not generated application data. They must be supplied with `MEMORY_CSV_PATH` and `MEMORY_ARCHIVE_PATH`. The Compose profile uses `create_host_path: false` so missing files fail before the importer starts. The service never writes to those source paths. PostgreSQL owns the imported records in the named volume.

### CTFAgent MCP and CLI Access

The backend agent tool registry exposes all memory MCP tools to every specialized solver agent:

```text
memory_search_writeups
memory_get_writeup
memory_list_domains
memory_search_source_documents
memory_get_source_document
memory_fetch_web_reference
```

The classifier also uses memory search results as background context.

The interactive CLI reaches the same JSON-RPC MCP endpoint through:

```text
/memory search <query>
/memory get <id>
/memory domains
/memory sources <query>
/memory source <id>
/memory fetch <https-url>
```

Set `MEMORY_SERVICE_URL` and `MEMORY_ENABLED=true` in the CTFAgent environment after the memory service is running. Memory is disabled by default so regular CTFAgent solves do not degrade or pause when the optional service is absent.

The default local URL is `http://127.0.0.1:3001`; Compose uses `http://memory:3000`.

### Native Linux / WSL

Use the native installer on Linux or WSL2 when you want CTFAgent installed directly into that environment.

```bash
git clone https://github.com/humaidhahm/ctfagent
cd ctfagent
python3 run.py
```

On first run, the installer:

1. Creates a Python virtual environment (`.venv`) to avoid the `externally-managed-environment` error on newer Debian/Ubuntu releases.
2. Installs all Python dependencies inside the virtual environment.
3. Installs missing system tools, which requires sudo.
4. Prompts for your NVIDIA NIM API key.
5. Launches the interactive CLI.

If your system Python lacks `venv` support:

```bash
sudo apt install python3-venv
```

### Verification

Run the local checks before opening or merging memory-service changes:

```bash
pytest
cd services/memory
npm test
npm run build
npx tsc --noEmit
npm audit --omit=dev
cd ../..
docker compose config
docker compose --profile memory config
```

These commands verify the Python agents, memory client, NestJS service tests, TypeScript build, production dependency audit, and Compose syntax. They do not start Postgres or import picoCTF data.

To verify the complete runtime pipeline, set `MEMORY_CSV_PATH`, `MEMORY_ARCHIVE_PATH`, and `MEMORY_ENABLED=true`, then run:

```bash
docker compose --profile api up --build
```

After startup, check:

```text
http://127.0.0.1:8000/health
```

Then run a memory lookup through the API or interactive CLI:

```text
/memory search buffer overflow
```

## Usage

The CLI supports two modes:

### Solve Mode

Enter the challenge description, paste a URL, or upload a file. The agent classifies the challenge, selects the appropriate tools, and works through it step by step.

### Hint Mode

Get a progressive hint without spoiling the full solution.

### Commands

| Command | Description |
|---------|-------------|
| `help` | Show help message |
| `install` | Re-run system tool installation |
| `tools` | List all available solving tools |
| `stats` | Show experience database stats |
| `history` | Show past solved challenges |
| `session` | Show active netcat sessions |
| `clear` | Clear the screen |
| `exit` / `quit` | Exit |

## Architecture

```text
CLI (cli/client.py)
  └── Supervisor (backend/agents/supervisor.py)
        ├── Classifier — identifies challenge category
        ├── Difficulty Estimator — estimates solve time
        ├── Domain Agents:
        │     ├── Web Agent
        │     ├── Pwn Agent
        │     ├── RE Agent
        │     ├── Forensics Agent
        │     ├── Crypto Agent
        │     └── OSINT/Misc Agent
        └── Flag Validator — detects and validates flags
```

## Tools by Category

**Web:** `sqlmap`, `ffuf`, `curl_probe`, `gobuster`

**Forensics:** `binwalk`, `exiftool`, `steghide`, `zsteg`, `tshark`, `file_decoder`, `foremost`

**Pwn:** `pwntools`, `checksec`, `ROPgadget`, `remote_connect`, `heartbleed`

**RE:** `radare2`, `strings`

**Crypto:** `cipher_cracker`, `rsa_solver`, `encoding_detector`

**OSINT:** `password_profiler`, `cupp`

**General:** `download_file`, `file_reader`, `binary_calc`

## Configuration

Native setup writes `.env` in the project root. Docker setup writes `data/.env` so configuration persists across container rebuilds and recreations.

For the Docker interactive CLI, attach stdin and a TTY:

```bash
docker compose run --rm ctfagent
```

You can also copy `.env.example` to the relevant environment file and configure it manually:

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_PROVIDER` | Yes | `nim`, `gemma`, or `gemini` |
| `NVIDIA_NIM_API_KEYS` | For NIM | Comma-separated NVIDIA NIM API keys |
| `NVIDIA_NIM_BASE_URL` | No | Base URL for NIM API |
| `GOOGLE_API_KEYS` | For Gemma/Gemini | Comma-separated Google AI API keys |
| `GOOGLE_MIN_REQUEST_INTERVAL_SECONDS` | No | Delay between Google LLM requests; default: `1.0` |
| `MAX_AGENT_ITERATIONS` | No | Maximum solve attempts; default: `20` |
| `FLAG_FORMAT` | No | Flag prefix, e.g. `picoCTF` or `CTF` |
| `MEMORY_SERVICE_URL` | For memory | Memory service URL; default local URL: `http://127.0.0.1:3001` |
| `MEMORY_ENABLED` | No | Enables the optional memory service |

Gemini/Gemma rate limits are quota-based at the Google project level. Multiple keys from the same project share that quota. Use `/llm` to reconfigure keys and check the configured key count shown at startup. If keys are from the same project, increase `GOOGLE_MIN_REQUEST_INTERVAL_SECONDS` to avoid shared quota bursts.

## Contributors

<table>
	<tr align="center">
		<td>
			CTFAgent Contributors
			<p align="center">
				<img src="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS2wTcTBKlN8lIbQQtmdxzt4-U6VqS3S6ZAk14xWbaEvg&s" width="150" height="150" alt="GDG VIT"/>
			</p>
			<p align="center">
				<a href="https://github.com/humaidhahm/ctfagent">
					<img src="https://uxwing.com/wp-content/themes/uxwing/download/brands-and-social-media/github-white-icon.png" width="36" height="36" alt="GitHub"/>
				</a>
			</p>
		</td>
	</tr>
</table>

<p align="center">
	Made with ❤ by <a href="https://dscvit.com">GDG-VIT</a>
</p>

## License

MIT
